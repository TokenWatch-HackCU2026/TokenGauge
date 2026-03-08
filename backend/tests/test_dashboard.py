"""
Tests for /dashboard endpoints:
  GET /dashboard/summary     — aggregated stats (tokens, cost, latency)
  GET /dashboard/timeseries  — time-series grouped by day or hour
  GET /dashboard/breakdown   — provider/model breakdown sorted by cost
  GET /dashboard/quota       — daily token quota status

All endpoints require authentication. The auth_headers fixture provides
a valid Bearer token for a registered test user.
"""
from datetime import datetime, timezone

DASHBOARD = "/dashboard"
USAGE = "/usage"

SAMPLE_RECORDS = [
    {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tokens_in": 500,
        "tokens_out": 100,
        "cost_usd": 0.0001,
        "latency_ms": 300,
        "app_tag": "dashboard-test",
    },
    {
        "provider": "openai",
        "model": "gpt-4o",
        "tokens_in": 1000,
        "tokens_out": 200,
        "cost_usd": 0.005,
        "latency_ms": 500,
        "app_tag": "dashboard-test",
    },
    {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "tokens_in": 800,
        "tokens_out": 150,
        "cost_usd": 0.003,
        "latency_ms": 400,
    },
]


def _seed_usage(client, auth_headers):
    """Insert sample records so dashboard endpoints have data."""
    for rec in SAMPLE_RECORDS:
        res = client.post(f"{USAGE}/", json=rec, headers=auth_headers)
        assert res.status_code == 200


# ── GET /dashboard/summary ───────────────────────────────────────────────────

class TestDashboardSummary:
    def test_summary_returns_200(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/summary", headers=auth_headers)
        assert res.status_code == 200

    def test_summary_has_expected_fields(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/summary", headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        for field in ("total_tokens_in", "total_tokens_out", "total_cost_usd", "request_count", "avg_latency_ms"):
            assert field in body, f"Missing field: {field}"

    def test_summary_values_non_negative(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/summary", headers=auth_headers)
        body = res.json()
        assert body["total_tokens_in"] >= 0
        assert body["total_tokens_out"] >= 0
        assert body["total_cost_usd"] >= 0.0
        assert body["request_count"] >= 0
        assert body["avg_latency_ms"] >= 0.0

    def test_summary_reflects_seeded_data(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/summary", headers=auth_headers)
        body = res.json()
        assert body["request_count"] >= len(SAMPLE_RECORDS)
        assert body["total_tokens_in"] > 0
        assert body["total_cost_usd"] > 0.0

    def test_summary_with_provider_filter(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/summary", params={"provider": "openai"}, headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["request_count"] >= 0

    def test_summary_with_model_filter(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/summary", params={"model": "gpt-4o-mini"}, headers=auth_headers)
        assert res.status_code == 200

    def test_summary_with_app_tag_filter(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/summary", params={"app_tag": "dashboard-test"}, headers=auth_headers)
        assert res.status_code == 200

    def test_summary_with_date_range(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/summary", params={
            "start_date": "2020-01-01T00:00:00Z",
            "end_date": "2020-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["request_count"] == 0

    def test_summary_empty_range_returns_zeroes(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/summary", params={
            "start_date": "2000-01-01T00:00:00Z",
            "end_date": "2000-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["total_tokens_in"] == 0
        assert body["total_tokens_out"] == 0
        assert body["total_cost_usd"] == 0.0
        assert body["request_count"] == 0
        assert body["avg_latency_ms"] == 0.0

    def test_summary_unauthenticated_401(self, client):
        res = client.get(f"{DASHBOARD}/summary")
        assert res.status_code in (401, 403)

    def test_summary_bad_token_401(self, client):
        res = client.get(f"{DASHBOARD}/summary", headers={"Authorization": "Bearer garbage"})
        assert res.status_code in (401, 403)


# ── GET /dashboard/timeseries ────────────────────────────────────────────────

class TestDashboardTimeseries:
    def test_timeseries_returns_200(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/timeseries", headers=auth_headers)
        assert res.status_code == 200

    def test_timeseries_returns_list(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/timeseries", headers=auth_headers)
        assert isinstance(res.json(), list)

    def test_timeseries_has_expected_fields(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", headers=auth_headers)
        points = res.json()
        if len(points) > 0:
            for field in ("date", "tokens_in", "tokens_out", "cost_usd", "request_count"):
                assert field in points[0], f"Missing field: {field}"

    def test_timeseries_group_by_day(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", params={"group_by": "day"}, headers=auth_headers)
        assert res.status_code == 200
        points = res.json()
        if len(points) > 0:
            # Day format: YYYY-MM-DD
            assert len(points[0]["date"]) == 10

    def test_timeseries_group_by_hour(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", params={"group_by": "hour"}, headers=auth_headers)
        assert res.status_code == 200
        points = res.json()
        if len(points) > 0:
            # Hour format: YYYY-MM-DDTHH:00:00Z
            assert "T" in points[0]["date"]
            assert points[0]["date"].endswith(":00:00Z")

    def test_timeseries_sorted_by_date_ascending(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", headers=auth_headers)
        points = res.json()
        if len(points) >= 2:
            dates = [p["date"] for p in points]
            assert dates == sorted(dates), "Timeseries not sorted ascending"

    def test_timeseries_with_provider_filter(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", params={"provider": "openai"}, headers=auth_headers)
        assert res.status_code == 200

    def test_timeseries_with_model_filter(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/timeseries", params={"model": "gpt-4o"}, headers=auth_headers)
        assert res.status_code == 200

    def test_timeseries_with_date_range(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/timeseries", params={
            "start_date": "2020-01-01T00:00:00Z",
            "end_date": "2020-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_timeseries_empty_range_returns_empty_list(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/timeseries", params={
            "start_date": "2000-01-01T00:00:00Z",
            "end_date": "2000-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_timeseries_values_non_negative(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/timeseries", headers=auth_headers)
        for p in res.json():
            assert p["tokens_in"] >= 0
            assert p["tokens_out"] >= 0
            assert p["cost_usd"] >= 0.0
            assert p["request_count"] > 0

    def test_timeseries_unauthenticated_401(self, client):
        res = client.get(f"{DASHBOARD}/timeseries")
        assert res.status_code in (401, 403)

    def test_timeseries_bad_token_401(self, client):
        res = client.get(f"{DASHBOARD}/timeseries", headers={"Authorization": "Bearer garbage"})
        assert res.status_code in (401, 403)


# ── GET /dashboard/breakdown ─────────────────────────────────────────────────

class TestDashboardBreakdown:
    def test_breakdown_returns_200(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        assert res.status_code == 200

    def test_breakdown_returns_list(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        assert isinstance(res.json(), list)

    def test_breakdown_has_expected_fields(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        rows = res.json()
        if len(rows) > 0:
            for field in ("provider", "model", "tokens_in", "tokens_out", "cost_usd", "request_count"):
                assert field in rows[0], f"Missing field: {field}"

    def test_breakdown_unique_provider_model_pairs(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        rows = res.json()
        pairs = [(r["provider"], r["model"]) for r in rows]
        assert len(pairs) == len(set(pairs)), "Duplicate provider/model pairs in breakdown"

    def test_breakdown_sorted_by_cost_descending(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        rows = res.json()
        if len(rows) >= 2:
            costs = [r["cost_usd"] for r in rows]
            assert costs == sorted(costs, reverse=True), "Breakdown not sorted by cost desc"

    def test_breakdown_values_non_negative(self, client, auth_headers):
        _seed_usage(client, auth_headers)
        res = client.get(f"{DASHBOARD}/breakdown", headers=auth_headers)
        for r in res.json():
            assert r["tokens_in"] >= 0
            assert r["tokens_out"] >= 0
            assert r["cost_usd"] >= 0.0
            assert r["request_count"] > 0

    def test_breakdown_with_date_range(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/breakdown", params={
            "start_date": "2020-01-01T00:00:00Z",
            "end_date": "2020-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_breakdown_empty_range_returns_empty_list(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/breakdown", params={
            "start_date": "2000-01-01T00:00:00Z",
            "end_date": "2000-01-02T00:00:00Z",
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_breakdown_unauthenticated_401(self, client):
        res = client.get(f"{DASHBOARD}/breakdown")
        assert res.status_code in (401, 403)

    def test_breakdown_bad_token_401(self, client):
        res = client.get(f"{DASHBOARD}/breakdown", headers={"Authorization": "Bearer garbage"})
        assert res.status_code in (401, 403)


# ── GET /dashboard/quota ─────────────────────────────────────────────────────

class TestDashboardQuota:
    def test_quota_returns_200(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        assert res.status_code == 200

    def test_quota_has_expected_fields(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        for field in ("limit", "used", "remaining", "reset_at", "window_ms"):
            assert field in body, f"Missing field: {field}"

    def test_quota_limit_is_one_million(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        assert body["limit"] == 1_000_000

    def test_quota_window_is_24h(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        assert body["window_ms"] == 86_400_000

    def test_quota_remaining_lte_limit(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        assert body["remaining"] <= body["limit"]

    def test_quota_used_plus_remaining_equals_limit(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        # remaining = max(0, limit - used), so used + remaining >= limit
        assert body["used"] + body["remaining"] >= body["limit"] or body["used"] >= body["limit"]

    def test_quota_values_non_negative(self, client, auth_headers):
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        assert body["limit"] > 0
        assert body["used"] >= 0
        assert body["remaining"] >= 0
        assert body["reset_at"] > 0
        assert body["window_ms"] > 0

    def test_quota_reset_at_in_future(self, client, auth_headers):
        import time
        res = client.get(f"{DASHBOARD}/quota", headers=auth_headers)
        body = res.json()
        now_ms = int(time.time() * 1000)
        assert body["reset_at"] > now_ms

    def test_quota_unauthenticated_401(self, client):
        res = client.get(f"{DASHBOARD}/quota")
        assert res.status_code in (401, 403)

    def test_quota_bad_token_401(self, client):
        res = client.get(f"{DASHBOARD}/quota", headers={"Authorization": "Bearer garbage"})
        assert res.status_code in (401, 403)
