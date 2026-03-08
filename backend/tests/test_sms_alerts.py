"""
Tests for SMS alert delivery at 80% and 100% quota thresholds.

These tests send REAL SMS messages to +17209650489 via Twilio.

Prerequisites:
    - Backend running at TEST_BASE_URL (default http://localhost:3001)
    - Redis running at localhost:6379 (docker run -d -p 6379:6379 redis:7-alpine)
    - Twilio credentials in backend/.env

Run:
    cd backend && pytest tests/test_sms_alerts.py -v -s
"""

import os
import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest
import redis
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:3001")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").replace("://redis:", "://localhost:")
PHONE = "+17209650489"
QUOTA_LIMIT = 1_000_000

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER", "")

SAMPLE_RECORD = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "tokens_in": 500,
    "tokens_out": 500,
    "cost_usd": 0.0,
    "latency_ms": 200,
    "app_tag": "sms-alert-test",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def r():
    """Direct Redis connection for seeding and verifying quota state."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()  # fail fast if Redis is down
    yield client
    client.close()


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as c:
        yield c


@pytest.fixture(scope="module")
def sms_user(api):
    """Register a user and set phone to the test number."""
    email = f"sms_{uuid.uuid4().hex[:8]}@example.com"
    res = api.post("/api/v1/auth/register", json={
        "email": email,
        "password": "SmsTest123!",
        "full_name": "SMS Alert Tester",
    })
    assert res.status_code == 201, f"Registration failed: {res.text}"
    data = res.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    phone_res = api.put("/api/v1/auth/phone", json={"phone": PHONE}, headers=headers)
    assert phone_res.status_code == 200, f"Phone update failed: {phone_res.text}"

    return {"user_id": data["user"]["id"], "headers": headers}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _quota_key(user_id):
    return f"quota:{user_id}:{_today()}"


def _dedup_key(user_id, alert_type):
    return f"alert_sent:{user_id}:{alert_type}:{_today()}"


def _send_twilio_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio REST API directly. Returns message SID."""
    resp = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
        auth=(TWILIO_SID, TWILIO_TOKEN),
        data={"To": to, "From": TWILIO_FROM, "Body": body},
        timeout=15.0,
    )
    assert resp.status_code == 201, f"Twilio error: {resp.text}"
    return resp.json()["sid"]


# ── Phone endpoint tests ─────────────────────────────────────────────────────

class TestPhoneEndpoint:
    def test_set_phone(self, api, sms_user):
        res = api.put("/api/v1/auth/phone", json={"phone": PHONE}, headers=sms_user["headers"])
        assert res.status_code == 200
        assert res.json()["phone"] == PHONE

    def test_rejects_bad_format(self, api, sms_user):
        for bad in ["7209650489", "720-965-0489", "not-a-number", "+1"]:
            res = api.put("/api/v1/auth/phone", json={"phone": bad}, headers=sms_user["headers"])
            assert res.status_code == 422, f"Expected 422 for '{bad}'"

    def test_requires_auth(self, api):
        res = api.put("/api/v1/auth/phone", json={"phone": PHONE})
        assert res.status_code == 401


# ── Redis quota tracking tests ───────────────────────────────────────────────

class TestRedisQuotaTracking:
    def test_usage_log_increments_quota(self, api, r, sms_user):
        """POST /usage/ should increment the daily quota counter in Redis."""
        uid = sms_user["user_id"]
        key = _quota_key(uid)

        # Clear any existing quota
        r.delete(key)

        # Log a 1,000-token call
        res = api.post("/usage/", json=SAMPLE_RECORD, headers=sms_user["headers"])
        assert res.status_code == 200

        # Give the async task time to run
        time.sleep(1)

        used = r.get(key)
        assert used is not None, "Quota key was not set in Redis"
        assert int(used) == 1000, f"Expected 1000, got {used}"

    def test_quota_accumulates(self, api, r, sms_user):
        """Multiple usage logs should accumulate in the same daily counter."""
        uid = sms_user["user_id"]
        key = _quota_key(uid)
        r.delete(key)

        for _ in range(3):
            api.post("/usage/", json=SAMPLE_RECORD, headers=sms_user["headers"])

        time.sleep(1)

        used = int(r.get(key) or 0)
        assert used == 3000, f"Expected 3000, got {used}"


# ── Alert threshold + SMS delivery tests ─────────────────────────────────────

class TestAlertThresholds:
    def test_80_percent_alert(self, api, r, sms_user):
        """Crossing 80% quota should set the dedup key and enqueue an alert."""
        uid = sms_user["user_id"]

        # Clean state
        r.delete(_quota_key(uid))
        r.delete(_dedup_key(uid, "quota_80"))
        r.delete(_dedup_key(uid, "quota_100"))

        # Seed Redis to just below 80% threshold
        r.set(_quota_key(uid), str(799_000))

        # Log 1,000 tokens → total becomes 800,000 (exactly 80%)
        res = api.post("/usage/", json=SAMPLE_RECORD, headers=sms_user["headers"])
        assert res.status_code == 200

        # Wait for async task
        time.sleep(3)

        dedup = r.get(_dedup_key(uid, "quota_80"))
        assert dedup == "1", (
            "80% dedup key not set — alert did not fire. "
            "Check that Twilio creds are in .env and arq worker is running."
        )
        print(f"\n  >>> 80% alert triggered for {PHONE}")

    def test_100_percent_alert(self, api, r, sms_user):
        """Crossing 100% quota should set the dedup key and enqueue an alert."""
        uid = sms_user["user_id"]

        # Clear only the 100% dedup (keep 80% to avoid duplicate)
        r.delete(_dedup_key(uid, "quota_100"))

        # Seed to just below 100%
        r.set(_quota_key(uid), str(999_000))

        res = api.post("/usage/", json=SAMPLE_RECORD, headers=sms_user["headers"])
        assert res.status_code == 200

        time.sleep(3)

        dedup = r.get(_dedup_key(uid, "quota_100"))
        assert dedup == "1", (
            "100% dedup key not set — alert did not fire. "
            "Check that Twilio creds are in .env and arq worker is running."
        )
        print(f"\n  >>> 100% alert triggered for {PHONE}")

    def test_dedup_prevents_repeat(self, api, r, sms_user):
        """Once an alert fires, logging more usage should NOT re-trigger it."""
        uid = sms_user["user_id"]

        # Both dedup keys should already be set from previous tests
        r.set(_quota_key(uid), str(1_500_000))

        res = api.post("/usage/", json=SAMPLE_RECORD, headers=sms_user["headers"])
        assert res.status_code == 200
        time.sleep(1)

        # Dedup keys still "1", no new alert
        assert r.get(_dedup_key(uid, "quota_80")) == "1"
        assert r.get(_dedup_key(uid, "quota_100")) == "1"


# ── Direct Twilio SMS tests ─────────────────────────────────────────────────

requires_twilio = pytest.mark.skipif(
    not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]),
    reason="Twilio credentials not configured",
)


class TestTwilioSms:
    @requires_twilio
    def test_send_80_percent_sms(self):
        """Actually send the 80% warning text to the test phone."""
        body = (
            f"TokenGauge Alert: You've used 80% of your daily token quota. "
            f"200,000 tokens remaining out of {QUOTA_LIMIT:,}."
        )
        sid = _send_twilio_sms(PHONE, body)
        assert sid.startswith("SM")
        print(f"\n  >>> 80% SMS delivered (SID: {sid})")

    @requires_twilio
    def test_send_100_percent_sms(self):
        """Actually send the 100% exhausted text to the test phone."""
        body = (
            f"TokenGauge Alert: You've hit 100% of your daily token quota "
            f"({QUOTA_LIMIT:,} tokens). API calls will be rate-limited until "
            f"your quota resets at midnight UTC."
        )
        sid = _send_twilio_sms(PHONE, body)
        assert sid.startswith("SM")
        print(f"\n  >>> 100% SMS delivered (SID: {sid})")
