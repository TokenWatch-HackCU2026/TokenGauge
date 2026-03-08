"""
TokenGauge SDK — zero-config AI usage tracking

Wraps your existing OpenAI / Anthropic client so every call is automatically
logged to your TokenGauge dashboard. Your API keys stay with you — the SDK
only reads token counts from responses and ships them to TokenGauge.

Install
-------
    pip install tokengauge          # coming soon
    pip install -e ./sdk            # local dev

Quick start
-----------
    from tokengauge import TokenGauge

    tw = TokenGauge.login("you@example.com", "password")

    # Drop-in OpenAI wrapper — use exactly as before
    import openai
    client = tw.wrap(openai.OpenAI(api_key="sk-..."))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Drop-in Anthropic wrapper
    import anthropic
    client = tw.wrap(anthropic.Anthropic(api_key="sk-ant-..."))
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Tag calls by app / feature
    client = tw.wrap(openai.OpenAI(api_key="sk-..."), app_tag="summarizer")

NOTE: The class is named TokenGauge but the file is tokenwatch.py for
backward compatibility with the published tokenwatch-sdk PyPI package.
"""

from __future__ import annotations

import threading
import time
from typing import Any

__version__ = "0.1.0"

# ── Pricing table (USD per 1 M tokens) ────────────────────────────────────────

_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":               {"input": 5.00,  "output": 15.00},
    "gpt-4o-mini":          {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":          {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":        {"input": 0.50,  "output": 1.50},
    "claude-3-haiku":       {"input": 0.25,  "output": 1.25},
    "claude-3-5-haiku":     {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet":    {"input": 3.00,  "output": 15.00},
    "claude-3-opus":        {"input": 15.00, "output": 75.00},
    "claude-opus-4":        {"input": 15.00, "output": 75.00},
    "gemini-1.5-flash":     {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":       {"input": 3.50,  "output": 10.50},
    "gemini-2.0-flash":     {"input": 0.10,  "output": 0.40},
    "mistral-small":        {"input": 1.00,  "output": 3.00},
    "mistral-medium":       {"input": 2.70,  "output": 8.10},
    "mistral-large":        {"input": 8.00,  "output": 24.00},
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


# ── Main client ───────────────────────────────────────────────────────────────

class TokenGauge:
    """
    Central TokenGauge client. Create one instance per app and reuse it.

    Parameters
    ----------
    token:    JWT access token obtained from TokenGauge login.
    base_url: Base URL of your TokenGauge server.
    app_tag:  Optional default tag applied to all logged calls (overridable per wrap).
    """

    def __init__(
        self,
        token: str,
        base_url: str = "http://localhost:8000",
        app_tag: str | None = None,
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.app_tag = app_tag

    # ── Auth ──────────────────────────────────────────────────────────────────

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        base_url: str = "http://localhost:8000",
        app_tag: str | None = None,
    ) -> "TokenGauge":
        """
        Authenticate and return a ready-to-use TokenGauge instance.

            tw = TokenGauge.login("you@example.com", "password")
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("pip install httpx")

        resp = httpx.post(
            f"{base_url.rstrip('/')}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        resp.raise_for_status()
        return cls(token=resp.json()["access_token"], base_url=base_url, app_tag=app_tag)

    # ── Wrap ──────────────────────────────────────────────────────────────────

    def wrap(self, client: Any, app_tag: str | None = None) -> Any:
        """
        Wrap any supported AI client for automatic usage tracking.

        Supported clients: openai.OpenAI, anthropic.Anthropic

            client = tw.wrap(openai.OpenAI(api_key="sk-..."))
            client = tw.wrap(anthropic.Anthropic(api_key="sk-ant-..."), app_tag="chatbot")
        """
        module = type(client).__module__
        tag = app_tag or self.app_tag

        if "openai" in module:
            return self._wrap_openai(client, tag)
        if "anthropic" in module:
            return self._wrap_anthropic(client, tag)

        raise ValueError(
            f"Unsupported client type '{type(client).__name__}'. "
            "Supported: openai.OpenAI, anthropic.Anthropic"
        )

    # ── OpenAI wrapper ────────────────────────────────────────────────────────

    def _wrap_openai(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        original_create = client.chat.completions.create

        def tracked_create(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            response = original_create(*args, **kwargs)
            latency_ms = int((time.time() - start) * 1000)

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

        client.chat.completions.create = tracked_create
        return client

    # ── Anthropic wrapper ─────────────────────────────────────────────────────

    def _wrap_anthropic(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        original_create = client.messages.create

        def tracked_create(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            response = original_create(*args, **kwargs)
            latency_ms = int((time.time() - start) * 1000)

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

        client.messages.create = tracked_create
        return client

    # ── Fire-and-forget logging ───────────────────────────────────────────────

    def _log(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        app_tag: str | None,
    ) -> None:
        cost_usd = _calc_cost(model, tokens_in, tokens_out)
        token = self.token
        base_url = self.base_url

        def _send() -> None:
            try:
                import httpx
                httpx.post(
                    f"{base_url}/usage/",
                    json={
                        "provider": provider,
                        "model": model,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost_usd": cost_usd,
                        "latency_ms": latency_ms,
                        "app_tag": app_tag,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                )
            except Exception:
                pass  # never block or crash the caller

        threading.Thread(target=_send, daemon=True).start()
