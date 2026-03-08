"""
Shared pytest fixtures for TokenWatch backend tests.
Runs against a live server at BASE_URL (default: http://localhost:3001).
Requires: pytest, httpx, python-dotenv
"""
import os
import uuid

import pytest
import httpx
from dotenv import load_dotenv

# Load .env from the project root (two levels up from backend/tests/)
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:3001")


@pytest.fixture(scope="session")
def client():
    """Synchronous httpx client for the whole test session."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="session")
def unique_email():
    """One-time unique email so parallel runs don't collide."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="session")
def registered_user(client, unique_email):
    """Register a user once and return the full response payload."""
    res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "TestPass123!",
        "full_name": "Test User",
    })
    assert res.status_code == 201, f"Registration failed: {res.text}"
    return res.json()


@pytest.fixture(scope="session")
def access_token(registered_user):
    return registered_user["access_token"]


@pytest.fixture(scope="session")
def refresh_token(registered_user):
    return registered_user["refresh_token"]


@pytest.fixture(scope="session")
def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


# ── API key fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_openai_key():
    """Real OpenAI key from .env — None if not set, skips dependent tests."""
    return os.getenv("TEST_OPENAI_KEY") or None


@pytest.fixture(scope="session")
def test_anthropic_key():
    """Real Anthropic key from .env — None if not set, skips dependent tests."""
    return os.getenv("TEST_ANTHROPIC_KEY") or None


@pytest.fixture(scope="session")
def test_google_key():
    """Real Google key from .env — None if not set, skips dependent tests."""
    return os.getenv("TEST_GOOGLE_KEY") or None


@pytest.fixture(scope="session")
def stored_openai_key(client, auth_headers, test_openai_key):
    """
    Store TEST_OPENAI_KEY in the DB via POST /keys/ and return the key record.
    Skips if TEST_OPENAI_KEY is not set in .env.
    """
    if not test_openai_key:
        pytest.skip("TEST_OPENAI_KEY not set in .env")
    res = client.post("/keys/", json={
        "provider": "openai",
        "api_key": test_openai_key,
    }, headers=auth_headers)
    assert res.status_code == 201, f"Failed to store OpenAI key: {res.text}"
    return res.json()


@pytest.fixture(scope="session")
def stored_anthropic_key(client, auth_headers, test_anthropic_key):
    """
    Store TEST_ANTHROPIC_KEY in the DB via POST /keys/ and return the key record.
    Skips if TEST_ANTHROPIC_KEY is not set in .env.
    """
    if not test_anthropic_key:
        pytest.skip("TEST_ANTHROPIC_KEY not set in .env")
    res = client.post("/keys/", json={
        "provider": "anthropic",
        "api_key": test_anthropic_key,
    }, headers=auth_headers)
    assert res.status_code == 201, f"Failed to store Anthropic key: {res.text}"
    return res.json()


@pytest.fixture(scope="session")
def stored_google_key(client, auth_headers, test_google_key):
    """
    Store TEST_GOOGLE_KEY in the DB via POST /keys/ and return the key record.
    Skips if TEST_GOOGLE_KEY is not set in .env.
    """
    if not test_google_key:
        pytest.skip("TEST_GOOGLE_KEY not set in .env")
    res = client.post("/keys/", json={
        "provider": "google",
        "api_key": test_google_key,
    }, headers=auth_headers)
    assert res.status_code == 201, f"Failed to store Google key: {res.text}"
    return res.json()
