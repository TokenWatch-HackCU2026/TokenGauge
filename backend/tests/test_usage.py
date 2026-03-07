"""
Tests for /usage endpoints:
  POST   /usage/         — log a new API call record
  GET    /usage/         — list records (with pagination)
  GET    /usage/summary  — aggregated summary by provider+model
  DELETE /usage/{id}     — delete a record
"""

USAGE = "/usage"

SAMPLE_RECORD = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "tokens_in": 512,
    "tokens_out": 128,
    "cost_usd": 0.000102,
    "latency_ms": 340,
    "app_tag": "test-suite",
}


# ── POST /usage/ ──────────────────────────────────────────────────────────────

class TestLogUsage:
    def test_log_usage_success(self, client):
        res = client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        assert res.status_code == 200
        body = res.json()
        assert "id" in body
        assert body["provider"] == SAMPLE_RECORD["provider"]
        assert body["model"] == SAMPLE_RECORD["model"]
        assert body["tokens_in"] == SAMPLE_RECORD["tokens_in"]
        assert body["tokens_out"] == SAMPLE_RECORD["tokens_out"]
        assert body["cost_usd"] == SAMPLE_RECORD["cost_usd"]
        assert body["latency_ms"] == SAMPLE_RECORD["latency_ms"]
        assert body["app_tag"] == SAMPLE_RECORD["app_tag"]
        assert "timestamp" in body

    def test_log_usage_without_app_tag(self, client):
        record = {k: v for k, v in SAMPLE_RECORD.items() if k != "app_tag"}
        res = client.post(f"{USAGE}/", json=record)
        assert res.status_code == 200
        assert res.json().get("app_tag") is None

    def test_log_usage_different_providers(self, client):
        for provider, model in [
            ("anthropic", "claude-3-5-sonnet"),
            ("google", "gemini-1.5-flash"),
            ("mistral", "mistral-small"),
        ]:
            res = client.post(f"{USAGE}/", json={
                **SAMPLE_RECORD,
                "provider": provider,
                "model": model,
            })
            assert res.status_code == 200, f"Failed for {provider}/{model}: {res.text}"
            assert res.json()["provider"] == provider

    def test_log_usage_missing_required_field_422(self, client):
        # Missing provider
        res = client.post(f"{USAGE}/", json={
            "model": "gpt-4o",
            "tokens_in": 10,
            "tokens_out": 20,
            "cost_usd": 0.001,
            "latency_ms": 100,
        })
        assert res.status_code == 422

    def test_log_usage_missing_tokens_in_422(self, client):
        record = {k: v for k, v in SAMPLE_RECORD.items() if k != "tokens_in"}
        res = client.post(f"{USAGE}/", json=record)
        assert res.status_code == 422

    def test_log_usage_zero_cost_allowed(self, client):
        res = client.post(f"{USAGE}/", json={**SAMPLE_RECORD, "cost_usd": 0.0})
        assert res.status_code == 200

    def test_log_usage_returns_user_id(self, client):
        res = client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        assert res.status_code == 200
        assert "user_id" in res.json()


# ── GET /usage/ ───────────────────────────────────────────────────────────────

class TestGetUsage:
    def test_get_usage_returns_list(self, client):
        res = client.get(f"{USAGE}/")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_get_usage_list_has_expected_fields(self, client):
        # Insert one record to ensure the list is non-empty
        client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        res = client.get(f"{USAGE}/")
        assert res.status_code == 200
        records = res.json()
        assert len(records) >= 1
        first = records[0]
        for field in ("id", "provider", "model", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "timestamp"):
            assert field in first, f"Missing field: {field}"

    def test_get_usage_default_limit_100(self, client):
        res = client.get(f"{USAGE}/")
        assert res.status_code == 200
        assert len(res.json()) <= 100

    def test_get_usage_limit_param(self, client):
        # Insert a couple of records first
        for _ in range(3):
            client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        res = client.get(f"{USAGE}/", params={"limit": 2})
        assert res.status_code == 200
        assert len(res.json()) <= 2

    def test_get_usage_skip_param(self, client):
        all_res = client.get(f"{USAGE}/", params={"limit": 5})
        skip_res = client.get(f"{USAGE}/", params={"limit": 5, "skip": 1})
        assert skip_res.status_code == 200
        all_records = all_res.json()
        skip_records = skip_res.json()
        # With enough records, skip=1 should shift results: record[1] of all == record[0] of skipped
        if len(all_records) > 1 and len(skip_records) > 0:
            assert all_records[1]["id"] == skip_records[0]["id"]

    def test_get_usage_ordered_by_timestamp_desc(self, client):
        # Post two records back to back
        client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        client.post(f"{USAGE}/", json={**SAMPLE_RECORD, "model": "gpt-4o"})
        res = client.get(f"{USAGE}/", params={"limit": 10})
        records = res.json()
        if len(records) >= 2:
            from datetime import datetime
            ts0 = datetime.fromisoformat(records[0]["timestamp"].replace("Z", "+00:00"))
            ts1 = datetime.fromisoformat(records[1]["timestamp"].replace("Z", "+00:00"))
            assert ts0 >= ts1, "Records are not sorted newest-first"


# ── GET /usage/summary ────────────────────────────────────────────────────────

class TestGetSummary:
    def test_summary_returns_list(self, client):
        res = client.get(f"{USAGE}/summary")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_summary_has_expected_fields(self, client):
        # Ensure at least one record exists
        client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        res = client.get(f"{USAGE}/summary")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1
        for field in ("provider", "model", "total_tokens_in", "total_tokens_out", "total_cost_usd", "request_count"):
            assert field in items[0], f"Missing field: {field}"

    def test_summary_aggregates_by_provider_and_model(self, client):
        res = client.get(f"{USAGE}/summary")
        items = res.json()
        # Each (provider, model) pair should appear at most once
        keys = [(i["provider"], i["model"]) for i in items]
        assert len(keys) == len(set(keys)), "Duplicate provider/model groups in summary"

    def test_summary_request_count_positive(self, client):
        client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        res = client.get(f"{USAGE}/summary")
        for item in res.json():
            assert item["request_count"] > 0

    def test_summary_totals_are_non_negative(self, client):
        res = client.get(f"{USAGE}/summary")
        for item in res.json():
            assert item["total_tokens_in"] >= 0
            assert item["total_tokens_out"] >= 0
            assert item["total_cost_usd"] >= 0.0


# ── DELETE /usage/{id} ────────────────────────────────────────────────────────

class TestDeleteUsage:
    def test_delete_existing_record(self, client):
        # Create a record to delete
        create_res = client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        assert create_res.status_code == 200
        record_id = create_res.json()["id"]

        del_res = client.delete(f"{USAGE}/{record_id}")
        assert del_res.status_code == 200
        assert del_res.json().get("ok") is True

    def test_delete_removes_record_from_list(self, client):
        create_res = client.post(f"{USAGE}/", json=SAMPLE_RECORD)
        record_id = create_res.json()["id"]

        client.delete(f"{USAGE}/{record_id}")

        # Record should no longer appear in the list
        all_ids = [r["id"] for r in client.get(f"{USAGE}/").json()]
        assert record_id not in all_ids

    def test_delete_nonexistent_record_404(self, client):
        fake_id = "000000000000000000000099"
        res = client.delete(f"{USAGE}/{fake_id}")
        assert res.status_code == 404

    def test_delete_invalid_id_format(self, client):
        res = client.delete(f"{USAGE}/not-a-valid-mongo-id")
        # FastAPI may return 404 (doc not found) or 422 (bad ID format)
        assert res.status_code in (404, 422)
