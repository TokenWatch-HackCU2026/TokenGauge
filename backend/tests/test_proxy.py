"""
Proxy endpoint tests — makes REAL API calls to each provider using keys from .env.

Flow for each provider:
  1. Store the API key in DB (via stored_*_key fixture)
  2. POST /proxy/{provider}/{path} → forwards to the real provider
  3. Assert the response contains actual content
  4. Assert usage (tokens + cost) was logged to MongoDB via GET /usage/

Tests auto-skip if the corresponding TEST_*_KEY is not set in .env.
"""

import time
import pytest

PROXY = "/proxy"
USAGE = "/usage"

SIMPLE_PROMPT = "Reply with exactly one word: hello"


# ── OpenAI ────────────────────────────────────────────────────────────────────

class TestProxyOpenAI:
    def test_openai_chat_completion(self, client, auth_headers, stored_openai_key):
        res = client.post(
            f"{PROXY}/openai/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
                "max_tokens": 10,
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-openai"},
        )
        assert res.status_code == 200, f"OpenAI proxy failed: {res.text}"
        body = res.json()
        assert "choices" in body, f"Unexpected response shape: {body}"
        assert len(body["choices"]) > 0
        assert body["choices"][0]["message"]["content"]

    def test_openai_usage_logged(self, client, auth_headers, stored_openai_key):
        """After a proxy call, usage should appear in GET /usage/."""
        # Make a call to ensure there's something to log
        client.post(
            f"{PROXY}/openai/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
                "max_tokens": 10,
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-openai-logging"},
        )
        # Brief pause for fire-and-forget log task to complete
        time.sleep(0.5)

        res = client.get(f"{USAGE}/", headers=auth_headers)
        assert res.status_code == 200
        records = res.json()
        openai_records = [r for r in records if r["provider"] == "openai"]
        assert len(openai_records) > 0, "No OpenAI usage records found after proxy call"

        latest = openai_records[0]
        assert latest["tokens_in"] > 0, "tokens_in should be > 0"
        assert latest["tokens_out"] > 0, "tokens_out should be > 0"
        assert latest["cost_usd"] >= 0.0
        # OpenAI returns versioned model names (e.g. gpt-4o-mini-2024-07-18)
        assert latest["model"].startswith("gpt-4o-mini")

    def test_openai_appears_in_summary(self, client, auth_headers, stored_openai_key):
        time.sleep(0.3)
        res = client.get(f"{USAGE}/summary", headers=auth_headers)
        assert res.status_code == 200
        providers = [r["provider"] for r in res.json()]
        assert "openai" in providers, "openai missing from usage summary"


# ── Anthropic ─────────────────────────────────────────────────────────────────

class TestProxyAnthropic:
    def test_anthropic_message(self, client, auth_headers, stored_anthropic_key):
        res = client.post(
            f"{PROXY}/anthropic/v1/messages",
            json={
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-anthropic"},
        )
        # Skip if the key has no credits
        if res.status_code == 400 and "credit balance" in res.text:
            pytest.skip("Anthropic key has no credits")
        assert res.status_code == 200, f"Anthropic proxy failed: {res.text}"
        body = res.json()
        assert "content" in body, f"Unexpected response shape: {body}"
        assert len(body["content"]) > 0
        assert body["content"][0]["text"]

    def test_anthropic_usage_logged(self, client, auth_headers, stored_anthropic_key):
        res = client.post(
            f"{PROXY}/anthropic/v1/messages",
            json={
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-anthropic-logging"},
        )
        if res.status_code == 400 and "credit balance" in res.text:
            pytest.skip("Anthropic key has no credits")
        time.sleep(0.5)

        res = client.get(f"{USAGE}/", headers=auth_headers)
        assert res.status_code == 200
        records = res.json()
        anthropic_records = [r for r in records if r["provider"] == "anthropic"]
        assert len(anthropic_records) > 0, "No Anthropic usage records found after proxy call"

        latest = anthropic_records[0]
        assert latest["tokens_in"] > 0
        assert latest["tokens_out"] > 0
        assert latest["cost_usd"] >= 0.0

    def test_anthropic_appears_in_summary(self, client, auth_headers, stored_anthropic_key):
        time.sleep(0.3)
        res = client.get(f"{USAGE}/summary", headers=auth_headers)
        assert res.status_code == 200
        providers = [r["provider"] for r in res.json()]
        assert "anthropic" in providers, "anthropic missing from usage summary"


# ── Google Gemini ─────────────────────────────────────────────────────────────

class TestProxyGoogle:
    def test_google_gemini_generate(self, client, auth_headers, stored_google_key):
        res = client.post(
            f"{PROXY}/google/v1beta/models/gemini-2.0-flash:generateContent",
            json={
                "contents": [{"parts": [{"text": SIMPLE_PROMPT}]}],
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-google"},
        )
        if res.status_code == 429:
            pytest.skip("Google key has exceeded its free tier quota")
        assert res.status_code == 200, f"Google proxy failed: {res.text}"
        body = res.json()
        assert "candidates" in body, f"Unexpected response shape: {body}"
        assert len(body["candidates"]) > 0
        assert body["candidates"][0]["content"]["parts"][0]["text"]

    def test_google_usage_logged(self, client, auth_headers, stored_google_key):
        res = client.post(
            f"{PROXY}/google/v1beta/models/gemini-2.0-flash:generateContent",
            json={
                "contents": [{"parts": [{"text": SIMPLE_PROMPT}]}],
            },
            headers={**auth_headers, "X-App-Tag": "proxy-test-google-logging"},
        )
        if res.status_code == 429:
            pytest.skip("Google key has exceeded its free tier quota")
        time.sleep(0.5)

        res = client.get(f"{USAGE}/", headers=auth_headers)
        assert res.status_code == 200
        records = res.json()
        google_records = [r for r in records if r["provider"] == "google"]
        assert len(google_records) > 0, "No Google usage records found after proxy call"

        latest = google_records[0]
        assert latest["tokens_in"] > 0
        assert latest["tokens_out"] > 0

    def test_google_appears_in_summary(self, client, auth_headers, stored_google_key):
        time.sleep(0.3)
        res = client.get(f"{USAGE}/summary", headers=auth_headers)
        assert res.status_code == 200
        providers = [r["provider"] for r in res.json()]
        assert "google" in providers, "google missing from usage summary"


# ── Auth enforcement ──────────────────────────────────────────────────────────

class TestProxyAuth:
    def test_proxy_unauthenticated_401(self, client):
        res = client.post(
            f"{PROXY}/openai/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": []},
        )
        assert res.status_code == 401

    def test_proxy_unsupported_provider_400(self, client, auth_headers):
        res = client.post(
            f"{PROXY}/fakeprovider/v1/chat",
            json={},
            headers=auth_headers,
        )
        assert res.status_code == 400

    def test_proxy_no_key_registered_404(self, client, auth_headers):
        """Requesting a provider with no stored key returns 404."""
        res = client.post(
            f"{PROXY}/mistral/v1/chat/completions",
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers=auth_headers,
        )
        assert res.status_code == 404
