"""
TokenGauge usage tracker.

Users obtain a token from their TokenGauge dashboard, then call tw.wrap()
around their existing AI client. All token usage is logged in the background —
API keys stay with the user, nothing is proxied.
"""

from __future__ import annotations

import inspect
import threading
import time
from typing import Any

__all__ = ["TokenGauge"]

# ── Pricing (USD per 1 M tokens) ─────────────────────────────────────────────
# Sources: openai.com/pricing, anthropic.com/pricing, ai.google.dev/pricing
# Versioned model IDs (e.g. gpt-4o-2024-11-20) fall back to prefix matching.

_PRICING: dict[str, dict[str, float]] = {
    # ── OpenAI ────────────────────────────────────────────────────────────────
    # GPT-5 family
    "gpt-5.4":                      {"input": 2.50,  "output": 15.00},
    "gpt-5.4-pro":                  {"input": 30.00, "output": 180.00},
    "gpt-5.3":                      {"input": 1.75,  "output": 14.00},
    "gpt-5.2":                      {"input": 1.75,  "output": 14.00},
    "gpt-5.1":                      {"input": 1.25,  "output": 10.00},
    "gpt-5":                        {"input": 1.25,  "output": 10.00},
    "gpt-5-mini":                   {"input": 0.25,  "output": 2.00},
    "gpt-5-nano":                   {"input": 0.05,  "output": 0.40},
    "gpt-5-pro":                    {"input": 15.00, "output": 120.00},
    # GPT-4.1 family
    "gpt-4.1":                      {"input": 2.00,  "output": 8.00},
    "gpt-4.1-mini":                 {"input": 0.40,  "output": 1.60},
    "gpt-4.1-nano":                 {"input": 0.10,  "output": 0.40},
    # GPT-4o family
    "gpt-4o":                       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":                  {"input": 0.15,  "output": 0.60},
    # o-series reasoning models
    "o1":                           {"input": 15.00, "output": 60.00},
    "o1-pro":                       {"input": 150.00,"output": 600.00},
    "o1-mini":                      {"input": 1.10,  "output": 4.40},
    "o1-preview":                   {"input": 15.00, "output": 60.00},
    "o3":                           {"input": 2.00,  "output": 8.00},
    "o3-pro":                       {"input": 20.00, "output": 80.00},
    "o3-mini":                      {"input": 1.10,  "output": 4.40},
    "o4-mini":                      {"input": 1.10,  "output": 4.40},
    # Codex
    "codex-mini-latest":            {"input": 1.50,  "output": 6.00},
    # GPT-4 legacy
    "gpt-4-turbo":                  {"input": 10.00, "output": 30.00},
    "gpt-4":                        {"input": 30.00, "output": 60.00},
    "gpt-4-32k":                    {"input": 60.00, "output": 120.00},
    # GPT-3.5
    "gpt-3.5-turbo":                {"input": 0.50,  "output": 1.50},

    # ── Anthropic ─────────────────────────────────────────────────────────────
    # Claude Opus 4.x
    "claude-opus-4.6":              {"input": 5.00,  "output": 25.00},
    "claude-opus-4.5":              {"input": 5.00,  "output": 25.00},
    "claude-opus-4.1":              {"input": 15.00, "output": 75.00},
    "claude-opus-4":                {"input": 15.00, "output": 75.00},
    # Claude Sonnet 4.x
    "claude-sonnet-4.6":            {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4.5":            {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4":              {"input": 3.00,  "output": 15.00},
    # Claude Haiku 4.x
    "claude-haiku-4.5":             {"input": 1.00,  "output": 5.00},
    # Claude 3.7
    "claude-3-7-sonnet":            {"input": 3.00,  "output": 15.00},
    # Claude 3.5
    "claude-3-5-sonnet":            {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku":             {"input": 0.80,  "output": 4.00},
    # Claude 3
    "claude-3-opus":                {"input": 15.00, "output": 75.00},
    "claude-3-sonnet":              {"input": 3.00,  "output": 15.00},
    "claude-3-haiku":               {"input": 0.25,  "output": 1.25},
    # Claude 2
    "claude-2":                     {"input": 8.00,  "output": 24.00},
    "claude-instant":               {"input": 0.80,  "output": 2.40},

    # ── Google Gemini ─────────────────────────────────────────────────────────
    # Gemini 3.x
    "gemini-3-pro":                 {"input": 2.00,  "output": 12.00},
    "gemini-3-flash":               {"input": 0.50,  "output": 3.00},
    "gemini-3.1-flash-lite":        {"input": 0.25,  "output": 1.50},
    # Gemini 2.5
    "gemini-2.5-pro":               {"input": 1.25,  "output": 10.00},
    "gemini-2.5-flash":             {"input": 0.30,  "output": 2.50},
    "gemini-2.5-flash-lite":        {"input": 0.10,  "output": 0.40},
    # Gemini 2.0
    "gemini-2.0-flash":             {"input": 0.10,  "output": 0.40},
    "gemini-2.0-flash-lite":        {"input": 0.075, "output": 0.30},
    # Gemini 1.5
    "gemini-1.5-pro":               {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":             {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b":          {"input": 0.0375,"output": 0.15},
    # Gemini 1.0
    "gemini-1.0-pro":               {"input": 0.50,  "output": 1.50},
    "gemini-pro":                   {"input": 0.50,  "output": 1.50},

    # ── Mistral ───────────────────────────────────────────────────────────────
    "mistral-large":                {"input": 2.00,  "output": 6.00},
    "mistral-small":                {"input": 0.10,  "output": 0.30},
    "mistral-medium":               {"input": 2.70,  "output": 8.10},
    "mistral-7b":                   {"input": 0.25,  "output": 0.25},
    "mixtral-8x7b":                 {"input": 0.70,  "output": 0.70},
    "mixtral-8x22b":                {"input": 2.00,  "output": 6.00},
    "codestral":                    {"input": 0.20,  "output": 0.60},
}


def _calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price = _PRICING.get(model)
    if price is None:
        for key, val in _PRICING.items():
            if model.startswith(key) or key.startswith(model):
                price = val
                break
    if price is None:
        return 0.0
    return (tokens_in / 1_000_000) * price["input"] + (tokens_out / 1_000_000) * price["output"]


# ── Main class ────────────────────────────────────────────────────────────────

class TokenGauge:
    """
    Wrap any OpenAI or Anthropic client to automatically track token usage.

    Your API keys never leave your environment — the SDK only reads token
    counts from responses and ships them to your TokenGauge dashboard.

    Parameters
    ----------
    token:    SDK token copied from your TokenGauge dashboard Settings page.
    base_url: URL of your TokenGauge server (no trailing slash).
    app_tag:  Optional label for this integration (e.g. "chatbot", "summarizer").
    verbose:  Print errors/status to stderr instead of silently ignoring them.

    Examples
    --------
    Basic usage::

        from tokengauge import TokenGauge
        import openai

        tw = TokenGauge(token="your-sdk-token", base_url="https://your-server.com")
        client = tw.wrap(openai.OpenAI(api_key="sk-..."))

        # Use exactly as before
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}],
        )

    Login instead of pasting a token::

        tw = TokenGauge.login(
            email="you@example.com",
            password="your-password",
            base_url="https://your-server.com",
        )
    """

    _BASE_URL = "https://tokengauge-api.onrender.com"

    def __init__(
        self,
        token: str,
        app_tag: str | None = None,
        verbose: bool = False,
    ) -> None:
        if not token:
            raise ValueError("token is required. Copy it from your TokenGauge dashboard Settings page.")
        self.token = token
        self.base_url = self._BASE_URL
        self.app_tag = app_tag
        self._verbose = verbose

    # ── Auth ──────────────────────────────────────────────────────────────────

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        app_tag: str | None = None,
        verbose: bool = False,
    ) -> "TokenGauge":
        """
        Authenticate with email + password and return a ready-to-use instance.
        Uses your persistent SDK token (1-year) so it never expires mid-session.

            tw = TokenGauge.login("you@example.com", "pass")
        """
        try:
            import httpx
        except ImportError:  # pragma: no cover
            raise ImportError("pip install httpx")

        base = cls._BASE_URL

        # Step 1: log in to get a short-lived access token
        resp = httpx.post(
            f"{base}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code == 401:
            raise ValueError("Invalid email or password.")
        resp.raise_for_status()
        access_token = resp.json()["access_token"]

        # Step 2: exchange for the persistent SDK token (1-year, never expires mid-session)
        sdk_resp = httpx.get(
            f"{base}/api/v1/auth/sdk-token",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if sdk_resp.is_success:
            token = sdk_resp.json()["sdk_token"]
        else:
            # Fall back to short-lived access token if SDK token fetch fails
            token = access_token

        return cls(token=token, app_tag=app_tag, verbose=verbose)

    # ── Wrap ──────────────────────────────────────────────────────────────────

    def wrap(self, client: Any, app_tag: str | None = None) -> Any:
        """
        Wrap a supported AI client for automatic usage tracking.

        Supports: openai.OpenAI, openai.AsyncOpenAI,
                  anthropic.Anthropic, anthropic.AsyncAnthropic

            client = tw.wrap(openai.OpenAI(api_key="sk-..."))
            client = tw.wrap(anthropic.Anthropic(api_key="sk-ant-..."), app_tag="chatbot")
        """
        tag = app_tag or self.app_tag
        cls_name = type(client).__name__
        module = type(client).__module__

        if "openai" in module:
            if "Async" in cls_name:
                return self._wrap_openai_async(client, tag)
            return self._wrap_openai_sync(client, tag)

        if "anthropic" in module:
            if "Async" in cls_name:
                return self._wrap_anthropic_async(client, tag)
            return self._wrap_anthropic_sync(client, tag)

        # google.genai (new SDK): Client
        if cls_name == "Client" and "google" in module:
            return self._wrap_genai_client(client, tag)

        # google.generativeai (legacy SDK): GenerativeModel
        if cls_name == "GenerativeModel" or ("google" in module and hasattr(client, "generate_content")):
            return self._wrap_gemini(client, tag)

        raise ValueError(
            f"Unsupported client '{cls_name}'. "
            "Supported: openai.OpenAI, openai.AsyncOpenAI, "
            "anthropic.Anthropic, anthropic.AsyncAnthropic, "
            "google.genai.Client, google.generativeai.GenerativeModel."
        )

    # ── OpenAI sync ───────────────────────────────────────────────────────────

    def _wrap_openai_sync(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.chat.completions.create

        def _create(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            model = getattr(response, "model", None) or kwargs.get("model", "unknown")
            usage = getattr(response, "usage", None)
            if usage:
                tw._log(
                    provider="openai",
                    model=model,
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.chat.completions.create = _create
        return client

    # ── OpenAI async ──────────────────────────────────────────────────────────

    def _wrap_openai_async(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.chat.completions.create

        async def _create(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = await _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            model = getattr(response, "model", None) or kwargs.get("model", "unknown")
            usage = getattr(response, "usage", None)
            if usage:
                tw._log_threaded(
                    provider="openai",
                    model=model,
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.chat.completions.create = _create
        return client

    # ── Anthropic sync ────────────────────────────────────────────────────────

    def _wrap_anthropic_sync(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.messages.create

        def _create(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            model = getattr(response, "model", None) or kwargs.get("model", "unknown")
            usage = getattr(response, "usage", None)
            if usage:
                tw._log(
                    provider="anthropic",
                    model=model,
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.messages.create = _create
        return client

    # ── Anthropic async ───────────────────────────────────────────────────────

    def _wrap_anthropic_async(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.messages.create

        async def _create(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = await _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            model = getattr(response, "model", None) or kwargs.get("model", "unknown")
            usage = getattr(response, "usage", None)
            if usage:
                tw._log_threaded(
                    provider="anthropic",
                    model=model,
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.messages.create = _create
        return client

    # ── Google Gemini (new google.genai SDK) ──────────────────────────────────

    def _wrap_genai_client(self, client: Any, app_tag: str | None) -> Any:
        """Wraps google.genai.Client — model name is passed per-call."""
        tw = self
        _orig = client.models.generate_content

        def _generate(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            model_name = kwargs.get("model", args[0] if args else "gemini")
            if isinstance(model_name, str) and "/" in model_name:
                model_name = model_name.split("/")[-1]
            meta = getattr(response, "usage_metadata", None)
            if meta:
                tw._log(
                    provider="google",
                    model=str(model_name),
                    tokens_in=getattr(meta, "prompt_token_count", 0),
                    tokens_out=getattr(meta, "candidates_token_count", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.models.generate_content = _generate
        return client

    # ── Google Gemini (legacy google.generativeai SDK) ────────────────────────

    def _wrap_gemini(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        model_name = getattr(client, "model_name", None) or getattr(client, "_model_name", "gemini")
        # Normalize "models/gemini-2.0-flash" -> "gemini-2.0-flash"
        if model_name and "/" in model_name:
            model_name = model_name.split("/")[-1]
        _orig = client.generate_content

        def _generate(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            meta = getattr(response, "usage_metadata", None)
            if meta:
                tw._log(
                    provider="google",
                    model=model_name or "gemini",
                    tokens_in=getattr(meta, "prompt_token_count", 0),
                    tokens_out=getattr(meta, "candidates_token_count", 0),
                    latency_ms=latency_ms,
                    app_tag=app_tag,
                )
            return response

        client.generate_content = _generate
        return client

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        app_tag: str | None,
    ) -> None:
        """Fire-and-forget: log in a background thread so the caller is never blocked."""
        threading.Thread(
            target=self._send,
            args=(provider, model, tokens_in, tokens_out, latency_ms, app_tag),
            daemon=False,
        ).start()

    # Alias used from async wrappers (same behaviour)
    _log_threaded = _log

    def _send(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        app_tag: str | None,
    ) -> None:
        import sys
        try:
            import httpx

            response = httpx.post(
                f"{self.base_url}/usage/",
                json={
                    "provider": provider,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": _calc_cost(model, tokens_in, tokens_out),
                    "latency_ms": latency_ms,
                    "app_tag": app_tag,
                },
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
            if self._verbose:
                if response.is_success:
                    print(f"[TokenGauge] Logged {provider}/{model}: {tokens_in}in {tokens_out}out", file=sys.stderr, flush=True)
                else:
                    print(f"[TokenGauge] Failed to log usage: HTTP {response.status_code} — {response.text}", file=sys.stderr, flush=True)
        except Exception as e:
            if self._verbose:
                print(f"[TokenGauge] Error sending usage data: {e}", file=sys.stderr, flush=True)
