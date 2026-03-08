"""
redis/worker.py
---------------
arq worker settings for TokenGauge async job queues.

Queues:
    - "alerts"          — SMS alert delivery (Twilio, post-MVP)
    - "webhooks"        — User webhook POST delivery
    - "usage-summaries" — Weekly usage aggregation reports
    - "spike-detection" — Hourly spike checker

Starting the worker:
    arq redis.worker.WorkerSettings

Or in docker-compose:
    command: arq redis.worker.WorkerSettings
"""

import logging
import os

import httpx
from arq.connections import RedisSettings
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------

async def deliver_webhook(ctx: dict, url: str, payload: dict) -> dict:
    """
    POST a usage event payload to a user-registered webhook URL.
    arq retries this up to max_tries times with exponential backoff.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Webhook delivered to %s — status %d", url, response.status_code)
            return {"status": response.status_code, "ok": True}
        except httpx.HTTPStatusError as exc:
            logger.warning("Webhook failed for %s — %s", url, exc)
            raise  # arq will retry
        except httpx.RequestError as exc:
            logger.error("Webhook request error for %s — %s", url, exc)
            raise


async def send_sms_alert(ctx: dict, user_id: str, phone: str, alert_type: str, message: str) -> None:
    """
    Send an SMS alert via Twilio.

    alert_type: "quota_80" | "quota_100" | "spike"
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("Twilio credentials not configured — skipping SMS for user %s", user_id)
        return

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(to=phone, from_=from_number, body=message)
        logger.info("SMS sent [%s] to %s for user %s — SID: %s", alert_type, phone, user_id, msg.sid)
    except Exception as exc:
        logger.error("Twilio SMS failed for user %s: %s", user_id, exc)
        raise  # arq will retry


async def run_usage_summary(ctx: dict, user_id: str, week_start: str) -> None:
    """
    Generate a weekly usage summary for a user.
    Reads api_calls from MongoDB and writes to usage_summaries.
    Placeholder — full implementation in the post-MVP optimizer task.
    """
    logger.info("Usage summary job started for user %s, week %s", user_id, week_start)
    # TODO: implement aggregation pipeline + MongoDB write


async def run_spike_detection(ctx: dict) -> None:
    """
    Hourly job: check every active user's 24h token usage against their
    7-day rolling baseline. Enqueue send_sms_alert if spike detected.
    """
    logger.info("Spike detection job running")
    # TODO: implement spike detection logic


# ---------------------------------------------------------------------------
# Worker settings — passed to `arq redis.worker.WorkerSettings`
# ---------------------------------------------------------------------------

class WorkerSettings:
    functions = [
        deliver_webhook,
        send_sms_alert,
        run_usage_summary,
        run_spike_detection,
    ]

    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    # Retry failed jobs up to 3 times with exponential backoff
    max_tries = 3

    # Job timeout (seconds)
    job_timeout = 30

    # Queue names that this worker listens on
    queue_name = "arq:queue"

    on_startup = None
    on_shutdown = None
