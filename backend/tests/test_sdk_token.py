"""
Tests for GET /api/v1/auth/sdk-token endpoint:
  - Returns a persistent SDK token (valid 1 year)
  - Supports ?regenerate=true to rotate the token

Requires authentication via Bearer token.
"""
import uuid

AUTH = "/api/v1/auth"


class TestSdkToken:
    def test_sdk_token_returns_200(self, client, auth_headers):
        res = client.get(f"{AUTH}/sdk-token", headers=auth_headers)
        assert res.status_code == 200

    def test_sdk_token_has_sdk_token_field(self, client, auth_headers):
        res = client.get(f"{AUTH}/sdk-token", headers=auth_headers)
        body = res.json()
        assert "sdk_token" in body
        assert isinstance(body["sdk_token"], str)
        assert len(body["sdk_token"]) > 0

    def test_sdk_token_is_stable(self, client, auth_headers):
        """Calling without regenerate should return the same token."""
        res1 = client.get(f"{AUTH}/sdk-token", headers=auth_headers)
        res2 = client.get(f"{AUTH}/sdk-token", headers=auth_headers)
        assert res1.json()["sdk_token"] == res2.json()["sdk_token"]

    def test_sdk_token_regenerate(self, client):
        """Regenerating should return a different token."""
        import time

        # Use a fresh user to avoid interfering with other tests
        email = f"sdk_{uuid.uuid4().hex[:8]}@test.com"
        reg = client.post(f"{AUTH}/register", json={
            "email": email,
            "password": "SdkPass123!",
        })
        assert reg.status_code == 201
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        res1 = client.get(f"{AUTH}/sdk-token", headers=headers)
        token1 = res1.json()["sdk_token"]

        # Wait so the new token gets a different exp timestamp
        time.sleep(1.1)

        res2 = client.get(f"{AUTH}/sdk-token", params={"regenerate": "true"}, headers=headers)
        assert res2.status_code == 200
        token2 = res2.json()["sdk_token"]
        assert token2 != token1

    def test_sdk_token_after_regenerate_is_stable(self, client):
        """After regeneration, the new token should persist."""
        email = f"sdk_{uuid.uuid4().hex[:8]}@test.com"
        reg = client.post(f"{AUTH}/register", json={
            "email": email,
            "password": "SdkPass123!",
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        client.get(f"{AUTH}/sdk-token", params={"regenerate": "true"}, headers=headers)
        res1 = client.get(f"{AUTH}/sdk-token", headers=headers)
        res2 = client.get(f"{AUTH}/sdk-token", headers=headers)
        assert res1.json()["sdk_token"] == res2.json()["sdk_token"]

    def test_sdk_token_unauthenticated_401(self, client):
        res = client.get(f"{AUTH}/sdk-token")
        assert res.status_code in (401, 403)

    def test_sdk_token_bad_token_401(self, client):
        res = client.get(f"{AUTH}/sdk-token", headers={"Authorization": "Bearer garbage"})
        assert res.status_code in (401, 403)
