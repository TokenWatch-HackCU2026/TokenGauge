"""Tests for GET /health"""


def test_health_returns_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_content_type_json(client):
    res = client.get("/health")
    assert "application/json" in res.headers.get("content-type", "")
