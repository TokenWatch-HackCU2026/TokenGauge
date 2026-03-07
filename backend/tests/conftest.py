"""
Shared pytest fixtures for TokenWatch backend tests.
Runs against a live server at BASE_URL (default: http://localhost:8000).
Requires: pytest, httpx
"""
import uuid
import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def client():
    """Synchronous httpx client for the whole test session."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="session")
def unique_email():
    """One-time unique email so parallel runs don't collide."""
    return f"test_{uuid.uuid4().hex[:8]}@tokenwatch.test"


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
