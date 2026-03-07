"""
Tests for /api/v1/auth endpoints:
  POST /register
  POST /login
  POST /refresh
  POST /logout
  GET  /google
  GET  /google/callback
"""
import uuid
import pytest


AUTH = "/api/v1/auth"


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
        res = client.post(f"{AUTH}/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "New User",
        })
        assert res.status_code == 201
        body = res.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert "user" in body
        assert body["user"]["email"] == email
        assert body["user"]["full_name"] == "New User"
        # Sensitive fields must never be returned
        assert "password_hash" not in body["user"]

    def test_register_returns_user_id(self, client):
        email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
        res = client.post(f"{AUTH}/register", json={
            "email": email,
            "password": "Password123!",
        })
        assert res.status_code == 201
        assert "id" in res.json()["user"]

    def test_register_duplicate_email_409(self, client, unique_email, registered_user):
        """Re-registering the session email must return 409."""
        res = client.post(f"{AUTH}/register", json={
            "email": unique_email,
            "password": "AnotherPass1!",
        })
        assert res.status_code == 409
        assert "already" in res.json()["detail"].lower()

    def test_register_invalid_email_422(self, client):
        res = client.post(f"{AUTH}/register", json={
            "email": "not-an-email",
            "password": "Password123!",
        })
        assert res.status_code == 422

    def test_register_missing_password_422(self, client):
        res = client.post(f"{AUTH}/register", json={
            "email": f"x_{uuid.uuid4().hex[:6]}@test.com",
        })
        assert res.status_code == 422

    def test_register_missing_email_422(self, client):
        res = client.post(f"{AUTH}/register", json={"password": "Password123!"})
        assert res.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client, unique_email):
        res = client.post(f"{AUTH}/login", json={
            "email": unique_email,
            "password": "TestPass123!",
        })
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body.get("expires_in") == 900  # 15 min

    def test_login_wrong_password_401(self, client, unique_email):
        res = client.post(f"{AUTH}/login", json={
            "email": unique_email,
            "password": "WrongPassword!",
        })
        assert res.status_code == 401
        assert "invalid" in res.json()["detail"].lower()

    def test_login_unknown_email_401(self, client):
        res = client.post(f"{AUTH}/login", json={
            "email": "nobody@nowhere.example.com",
            "password": "SomePass123!",
        })
        assert res.status_code == 401

    def test_login_invalid_email_format_422(self, client):
        res = client.post(f"{AUTH}/login", json={
            "email": "notanemail",
            "password": "SomePass123!",
        })
        assert res.status_code == 422

    def test_login_missing_body_422(self, client):
        res = client.post(f"{AUTH}/login", json={})
        assert res.status_code == 422


# ── Refresh ───────────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_success(self, client, refresh_token):
        res = client.post(f"{AUTH}/refresh", json={"refresh_token": refresh_token})
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body.get("expires_in") == 900

    def test_refresh_invalid_token_401(self, client):
        res = client.post(f"{AUTH}/refresh", json={"refresh_token": "garbage.token.value"})
        assert res.status_code == 401

    def test_refresh_empty_token_401_or_422(self, client):
        res = client.post(f"{AUTH}/refresh", json={"refresh_token": ""})
        assert res.status_code in (401, 422)

    def test_refresh_missing_body_422(self, client):
        res = client.post(f"{AUTH}/refresh", json={})
        assert res.status_code == 422


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_success_204(self, client, unique_email):
        """Log in fresh, then log out — expect 204."""
        login = client.post(f"{AUTH}/login", json={
            "email": unique_email,
            "password": "TestPass123!",
        })
        assert login.status_code == 200
        rt = login.json()["refresh_token"]

        res = client.post(f"{AUTH}/logout", json={"refresh_token": rt})
        assert res.status_code == 204

    def test_logout_invalidates_refresh_token(self, client, unique_email):
        """After logout, the same refresh token should be rejected."""
        login = client.post(f"{AUTH}/login", json={
            "email": unique_email,
            "password": "TestPass123!",
        })
        rt = login.json()["refresh_token"]

        client.post(f"{AUTH}/logout", json={"refresh_token": rt})

        # Refreshing with the now-invalidated token must fail
        retry = client.post(f"{AUTH}/refresh", json={"refresh_token": rt})
        assert retry.status_code == 401

    def test_logout_with_garbage_token_still_204(self, client):
        """Invalid tokens are silently swallowed — idempotent logout."""
        res = client.post(f"{AUTH}/logout", json={"refresh_token": "garbage.token"})
        assert res.status_code == 204

    def test_logout_missing_body_422(self, client):
        res = client.post(f"{AUTH}/logout", json={})
        assert res.status_code == 422


# ── Google OAuth ───────────────────────────────────────────────────────────────

class TestGoogleOAuth:
    def test_google_login_returns_url_or_500(self, client):
        """Returns redirect URL if GOOGLE_CLIENT_ID is set, else 500."""
        res = client.get(f"{AUTH}/google")
        if res.status_code == 200:
            body = res.json()
            assert "url" in body
            assert "accounts.google.com" in body["url"]
        else:
            # Server lacks GOOGLE_CLIENT_ID env var — acceptable in dev
            assert res.status_code == 500

    def test_google_callback_bad_code_400(self, client):
        """Fake OAuth code must be rejected by Google and return 400."""
        res = client.get(f"{AUTH}/google/callback", params={"code": "fake-code-123"})
        # Either 400 (token exchange failed) or 500 (missing env vars)
        assert res.status_code in (400, 500)
