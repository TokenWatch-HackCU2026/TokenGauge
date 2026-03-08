"""
TokenGauge usage tracker.

Users obtain a token from their TokenGauge dashboard, then call tw.wrap()
around their existing AI client. All token usage is logged in the background —
API keys stay with the user, nothing is proxied.
"""

from __future__ import annotations

import inspect
import re
import threading
import time
from datetime import datetime
from typing import Any

__all__ = ["TokenGauge", "BudgetExceededError"]


class BudgetExceededError(Exception):
    """Raised when a provider spend limit would be exceeded by the estimated call cost."""
    def __init__(self, provider: str, estimated_cost: float, remaining: float, period: str) -> None:
        self.provider = provider
        self.estimated_cost = estimated_cost
        self.remaining = remaining
        self.period = period
        super().__init__(
            f"[TokenGauge] {period.capitalize()} budget exceeded for {provider}: "
            f"estimated cost ${estimated_cost:.4f} > ${remaining:.4f} remaining"
        )


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
    "claude-haiku-4-5-20251001":    {"input": 1.00,  "output": 5.00},
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
    "gemini-flash-latest":          {"input": 0.10,  "output": 0.40},
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


# ── Model Registry (for recommendations) ─────────────────────────────────────
# Each entry: provider, base quality (1-10), per-type score overrides,
# and max_complexity (complexity levels above this incur a success penalty).

_MODEL_REGISTRY: dict[str, dict] = {
    # ── OpenAI ────────────────────────────────────────────────────────────────
    "gpt-4.1":      {"provider": "openai",    "quality": 9, "max_complexity": 10,
                     "type_scores": {"code": 10, "analysis": 9, "extraction": 9}},
    "gpt-4.1-mini": {"provider": "openai",    "quality": 7, "max_complexity": 8,
                     "type_scores": {"code": 8,  "chat": 8,   "extraction": 8}},
    "gpt-4.1-nano": {"provider": "openai",    "quality": 5, "max_complexity": 6,
                     "type_scores": {"chat": 7,  "summarization": 6}},
    "gpt-4o":       {"provider": "openai",    "quality": 8, "max_complexity": 9,
                     "type_scores": {"code": 9,  "analysis": 9,  "chat": 9,  "creative": 8}},
    "gpt-4o-mini":  {"provider": "openai",    "quality": 6, "max_complexity": 7,
                     "type_scores": {"chat": 8,  "summarization": 7, "translation": 7}},
    "o3":           {"provider": "openai",    "quality": 9, "max_complexity": 10,
                     "type_scores": {"code": 10, "analysis": 10, "extraction": 9}},
    "o3-mini":      {"provider": "openai",    "quality": 7, "max_complexity": 9,
                     "type_scores": {"code": 9,  "analysis": 8}},
    "o4-mini":      {"provider": "openai",    "quality": 7, "max_complexity": 9,
                     "type_scores": {"code": 9,  "analysis": 8}},

    # ── Anthropic ─────────────────────────────────────────────────────────────
    "claude-opus-4.6":           {"provider": "anthropic", "quality": 10, "max_complexity": 10,
                                  "type_scores": {"code": 10, "analysis": 10, "creative": 10, "chat": 10}},
    "claude-sonnet-4.6":         {"provider": "anthropic", "quality": 8,  "max_complexity": 9,
                                  "type_scores": {"code": 9,  "analysis": 9,  "chat": 9, "creative": 8}},
    "claude-haiku-4-5-20251001": {"provider": "anthropic", "quality": 6,  "max_complexity": 7,
                                  "type_scores": {"chat": 8,  "summarization": 7, "translation": 7}},
    "claude-3-7-sonnet":         {"provider": "anthropic", "quality": 8,  "max_complexity": 9,
                                  "type_scores": {"code": 9,  "analysis": 9}},
    "claude-3-5-sonnet":         {"provider": "anthropic", "quality": 8,  "max_complexity": 9,
                                  "type_scores": {"code": 9,  "analysis": 8}},
    "claude-3-5-haiku":          {"provider": "anthropic", "quality": 6,  "max_complexity": 7,
                                  "type_scores": {"chat": 8,  "summarization": 7}},

    # ── Google ────────────────────────────────────────────────────────────────
    "gemini-2.5-pro":       {"provider": "google", "quality": 9, "max_complexity": 10,
                             "type_scores": {"code": 9, "analysis": 9, "extraction": 9, "creative": 8}},
    "gemini-2.5-flash":     {"provider": "google", "quality": 7, "max_complexity": 8,
                             "type_scores": {"code": 8, "summarization": 8, "translation": 8, "extraction": 8}},
    "gemini-2.0-flash":     {"provider": "google", "quality": 6, "max_complexity": 7,
                             "type_scores": {"chat": 8, "summarization": 7, "translation": 8}},
    "gemini-2.0-flash-lite":{"provider": "google", "quality": 5, "max_complexity": 6,
                             "type_scores": {"chat": 7, "translation": 7}},
}


# ── Prompt Classification ─────────────────────────────────────────────────────
# Runs locally in the SDK — raw prompt text is NEVER sent to TokenGauge.

_PROMPT_TYPES = (
    "code", "chat", "summarization", "analysis",
    "creative", "extraction", "translation", "other",
)

# Patterns checked in priority order; first match wins.
_CLASSIFICATION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("code", re.compile(
        r"```"                            # code fences
        r"|write (?:a |the )?(?:function|class|script|program|code|test|module)"
        r"|fix (?:this |the )?(?:bug|error|code|issue)"
        r"|refactor"
        r"|debug"
        r"|implement"
        r"|(?:python|javascript|typescript|java|rust|go|c\+\+|sql|html|css|bash|shell)\b",
        re.IGNORECASE,
    )),
    ("translation", re.compile(
        r"\btranslat(?:e|ion)\b"
        r"|(?:in|to|into) (?:spanish|french|german|chinese|japanese|korean|portuguese|italian|russian|arabic|hindi|english)\b",
        re.IGNORECASE,
    )),
    ("summarization", re.compile(
        r"\bsummari[sz]e\b"
        r"|\bsummary\b"
        r"|\btl;?dr\b"
        r"|\bkey (?:points|takeaways)\b"
        r"|\bcondense\b"
        r"|\bbrief (?:overview|recap)\b",
        re.IGNORECASE,
    )),
    ("extraction", re.compile(
        r"\bextract\b"
        r"|\bparse\b"
        r"|\blist (?:the|all)\b"
        r"|\bpull out\b"
        r"|\b(?:convert|format) (?:to|into|as) (?:json|csv|xml|yaml|table)\b",
        re.IGNORECASE,
    )),
    ("analysis", re.compile(
        r"\banaly[sz]e\b"
        r"|\banalysis\b"
        r"|\bcompare\b"
        r"|\bevaluat(?:e|ion)\b"
        r"|\bpros (?:and|&) cons\b"
        r"|\bbreak ?down\b"
        r"|\bassess\b"
        r"|\bexplain (?:why|how)\b",
        re.IGNORECASE,
    )),
    ("creative", re.compile(
        r"\bwrite (?:a |the )?(?:story|poem|essay|blog|article|song|script|novel|email)\b"
        r"|\bbrainstorm\b"
        r"|\bcreative\b"
        r"|\bimagine\b"
        r"|\bgenerate (?:a |the )?(?:story|idea|name|title|slogan|tagline)\b",
        re.IGNORECASE,
    )),
]


def _extract_text(messages: Any) -> str:
    """Pull plaintext from messages in any supported provider format."""
    if isinstance(messages, str):
        return messages
    if not isinstance(messages, (list, tuple)):
        return str(messages)
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, str):
            parts.append(msg)
        elif isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
        elif hasattr(msg, "text"):
            parts.append(str(msg.text))
    return "\n".join(parts)


def _classify_prompt(messages: Any) -> str:
    """Classify prompt into one of the 8 categories using keyword heuristics."""
    text = _extract_text(messages)
    if not text.strip():
        return "other"
    for label, pattern in _CLASSIFICATION_RULES:
        if pattern.search(text):
            return label
    # Default: short messages are chat, longer ones are other
    if len(text) < 500:
        return "chat"
    return "other"


def _score_complexity(messages: Any, prompt_type: str, tokens_in: int) -> int:
    """Score prompt complexity 1–10 based on metadata heuristics."""
    text = _extract_text(messages)
    score = 1

    # Token count signal
    if tokens_in > 4000:
        score += 3
    elif tokens_in > 1500:
        score += 2
    elif tokens_in > 500:
        score += 1

    # Message count (multi-turn = more complex)
    if isinstance(messages, (list, tuple)):
        n_msgs = len(messages)
        if n_msgs > 10:
            score += 2
        elif n_msgs > 3:
            score += 1

    # Code fences suggest structured/complex requests
    code_blocks = text.count("```")
    if code_blocks >= 4:
        score += 2
    elif code_blocks >= 2:
        score += 1

    # Prompt type bias
    type_bias = {"code": 2, "analysis": 1, "extraction": 1, "creative": 1}
    score += type_bias.get(prompt_type, 0)

    # Text length (chars) as a secondary signal
    if len(text) > 3000:
        score += 1

    return min(score, 10)


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
    classify: Enable local prompt classification and complexity scoring (default True).
              When enabled, the SDK inspects prompt text locally to compute prompt_type
              and complexity. Raw prompt text is NEVER sent to TokenGauge.
              Set to False to disable — only token counts and metadata will be logged.
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
        base_url: str | None = None,
        app_tag: str | None = None,
        classify: bool = True,
        verbose: bool = False,
    ) -> None:
        if not token:
            raise ValueError("token is required. Copy it from your TokenGauge dashboard Settings page.")
        self.token = token
        self.base_url = (base_url or self._BASE_URL).rstrip("/")
        self.app_tag = app_tag
        self.classify = classify
        self._verbose = verbose
        self._spend_status_cache: dict | None = None
        self._spend_status_fetched_at: float = 0

    # ── Auth ──────────────────────────────────────────────────────────────────

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        base_url: str | None = None,
        app_tag: str | None = None,
        classify: bool = True,
        verbose: bool = False,
    ) -> "TokenGauge":
        """
        Authenticate with email + password and return a ready-to-use instance.
        Uses your persistent SDK token (1-year) so it never expires mid-session.

            tw = TokenGauge.login("you@example.com", "pass")
            tw = TokenGauge.login("you@example.com", "pass", base_url="http://localhost:8000")
        """
        try:
            import httpx
        except ImportError:  # pragma: no cover
            raise ImportError("pip install httpx")

        base = (base_url or cls._BASE_URL).rstrip("/")

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

        return cls(token=token, base_url=base, app_tag=app_tag, classify=classify, verbose=verbose)

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
        key_hint = self._extract_key_hint(client)

        def _create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages")
            tw._check_budget("openai", kwargs.get("model", "unknown"), messages)
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=messages,
                    timestamp=ts,
                )
            return response

        client.chat.completions.create = _create
        return client

    # ── OpenAI async ──────────────────────────────────────────────────────────

    def _wrap_openai_async(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.chat.completions.create
        key_hint = self._extract_key_hint(client)

        async def _create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages")
            tw._check_budget("openai", kwargs.get("model", "unknown"), messages)
            start = time.monotonic()
            response = await _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=messages,
                    timestamp=ts,
                )
            return response

        client.chat.completions.create = _create
        return client

    # ── Anthropic sync ────────────────────────────────────────────────────────

    def _wrap_anthropic_sync(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.messages.create
        key_hint = self._extract_key_hint(client)

        def _create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages")
            # Anthropic has system prompt as a separate kwarg
            system = kwargs.get("system")
            if system and messages:
                messages = [{"role": "system", "content": system}] + list(messages)
            tw._check_budget("anthropic", kwargs.get("model", "unknown"), messages)
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=messages,
                    timestamp=ts,
                )
            return response

        client.messages.create = _create
        return client

    # ── Anthropic async ───────────────────────────────────────────────────────

    def _wrap_anthropic_async(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        _orig = client.messages.create
        key_hint = self._extract_key_hint(client)

        async def _create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages")
            system = kwargs.get("system")
            if system and messages:
                messages = [{"role": "system", "content": system}] + list(messages)
            tw._check_budget("anthropic", kwargs.get("model", "unknown"), messages)
            start = time.monotonic()
            response = await _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=messages,
                    timestamp=ts,
                )
            return response

        client.messages.create = _create
        return client

    # ── Google Gemini (new google.genai SDK) ──────────────────────────────────

    def _wrap_genai_client(self, client: Any, app_tag: str | None) -> Any:
        """Wraps google.genai.Client — model name is passed per-call."""
        tw = self
        _orig = client.models.generate_content
        key_hint = self._extract_key_hint(client)

        def _generate(*args: Any, **kwargs: Any) -> Any:
            # google.genai: contents is 2nd positional arg or kwarg
            contents = kwargs.get("contents", args[1] if len(args) > 1 else None)
            _model_arg = kwargs.get("model", args[0] if args else "gemini")
            tw._check_budget("google", str(_model_arg).split("/")[-1], contents)
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=contents,
                    timestamp=ts,
                )
            return response

        client.models.generate_content = _generate
        return client

    # ── Google Gemini (legacy google.generativeai SDK) ────────────────────────

    def _wrap_gemini(self, client: Any, app_tag: str | None) -> Any:
        tw = self
        key_hint = self._extract_key_hint(client)
        model_name = getattr(client, "model_name", None) or getattr(client, "_model_name", "gemini")
        # Normalize "models/gemini-2.0-flash" -> "gemini-2.0-flash"
        if model_name and "/" in model_name:
            model_name = model_name.split("/")[-1]
        _orig = client.generate_content

        def _generate(*args: Any, **kwargs: Any) -> Any:
            # Legacy SDK: first positional arg is the content/prompt
            contents = args[0] if args else kwargs.get("contents")
            tw._check_budget("google", model_name or "gemini", contents)
            start = time.monotonic()
            response = _orig(*args, **kwargs)
            ts = datetime.now().astimezone().isoformat()
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
                    key_hint=key_hint,
                    messages=contents,
                    timestamp=ts,
                )
            return response

        client.generate_content = _generate
        return client

    # ── Budget check ──────────────────────────────────────────────────────────

    _SPEND_CACHE_TTL = 60.0  # seconds

    def _get_spend_status(self) -> dict | None:
        """Fetch /dashboard/spend-status, cached for 60 s."""
        now = time.monotonic()
        if (
            self._spend_status_cache is not None
            and (now - self._spend_status_fetched_at) < self._SPEND_CACHE_TTL
        ):
            return self._spend_status_cache
        try:
            import httpx
            resp = httpx.get(
                f"{self.base_url}/dashboard/spend-status",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
            if resp.is_success:
                self._spend_status_cache = resp.json()
                self._spend_status_fetched_at = now
                return self._spend_status_cache
        except Exception:
            pass
        return self._spend_status_cache  # return stale cache on error

    def _check_budget(self, provider: str, model: str, messages: Any) -> None:
        """Estimate call cost and raise BudgetExceededError if the spend limit would be exceeded."""
        text = _extract_text(messages)
        est_in = max(10, len(text) // 4)
        est_out = max(10, est_in * 2 // 5)
        est_cost = _calc_cost(model, est_in, est_out)
        status = self._get_spend_status()
        if not status:
            return
        for entry in status.get("statuses", []):
            if entry.get("provider") == provider and entry.get("enabled"):
                remaining = float(entry.get("remaining_usd", float("inf")))
                if est_cost > remaining:
                    raise BudgetExceededError(
                        provider=provider,
                        estimated_cost=est_cost,
                        remaining=remaining,
                        period=entry.get("period", "unknown"),
                    )
                break

    # ── Logging ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_key_hint(client: Any) -> str | None:
        """Return last 4 chars of the provider API key, or None if not found."""
        # OpenAI, Anthropic: client.api_key
        key = getattr(client, "api_key", None)
        if key and isinstance(key, str) and len(key) >= 4:
            return key[-4:]
        # Google genai.Client: client._api_client.api_key
        inner = getattr(client, "_api_client", None)
        if inner:
            key = getattr(inner, "api_key", None)
            if key and isinstance(key, str) and len(key) >= 4:
                return key[-4:]
        return None

    def _log(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        app_tag: str | None,
        key_hint: str | None = None,
        messages: Any = None,
        timestamp: str | None = None,
    ) -> None:
        """Fire-and-forget: log in a background thread so the caller is never blocked."""
        # Classify locally before spawning the thread (prompt text stays here)
        prompt_type: str | None = None
        complexity: int | None = None
        if self.classify and messages is not None:
            prompt_type = _classify_prompt(messages)
            complexity = _score_complexity(messages, prompt_type, tokens_in)

        threading.Thread(
            target=self._send,
            args=(provider, model, tokens_in, tokens_out, latency_ms, app_tag,
                  key_hint, prompt_type, complexity, timestamp),
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
        key_hint: str | None = None,
        prompt_type: str | None = None,
        complexity: int | None = None,
        timestamp: str | None = None,
    ) -> None:
        import sys
        try:
            import httpx

            payload: dict[str, Any] = {
                "provider": provider,
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": _calc_cost(model, tokens_in, tokens_out),
                "latency_ms": latency_ms,
                "app_tag": app_tag,
                "key_hint": key_hint,
            }
            if prompt_type is not None:
                payload["prompt_type"] = prompt_type
            if complexity is not None:
                payload["complexity"] = complexity
            if timestamp is not None:
                payload["timestamp"] = timestamp

            response = httpx.post(
                f"{self.base_url}/usage/",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
            if self._verbose:
                if response.is_success:
                    extra = f" [{prompt_type}|c={complexity}]" if prompt_type else ""
                    print(f"[TokenGauge] Logged {provider}/{model}: {tokens_in}in {tokens_out}out{extra}", file=sys.stderr, flush=True)
                else:
                    print(f"[TokenGauge] Failed to log usage: HTTP {response.status_code} — {response.text}", file=sys.stderr, flush=True)
        except Exception as e:
            if self._verbose:
                print(f"[TokenGauge] Error sending usage data: {e}", file=sys.stderr, flush=True)

    # ── Model Recommendation ───────────────────────────────────────────────

    def recommend_model(
        self,
        messages: Any,
        provider: str | None = None,
        budget_usd: float | None = None,
    ) -> dict:
        """
        Recommend the best model for a given prompt — no API call required.

        Classifies the prompt locally, estimates token usage and cost, then
        scores every model in the registry by success probability (based on
        prompt type + complexity). Returns the best match within your preferred
        provider and the best match across all providers.

        Parameters
        ----------
        messages:   Prompt in any supported format (str, list of dicts, etc.).
        provider:   Preferred provider ("openai", "anthropic", "google").
                    If given, ``within_provider`` in the result will be filled.
        budget_usd: Maximum estimated cost per request (USD). Models whose
                    estimated cost exceeds this are excluded.

        Returns
        -------
        dict with keys:
            prompt_type         – classified category (e.g. "code", "chat")
            complexity          – estimated complexity score 1–10
            estimated_tokens_in – rough token estimate for the prompt
            within_provider     – best model for ``provider`` (None if not given)
            best_overall        – best model across all providers

        Each model entry contains:
            model, provider, quality_score, estimated_tokens_in,
            estimated_tokens_out, estimated_cost_usd, success_probability

        Example
        -------
        ::

            rec = tw.recommend_model(
                messages=[{"role": "user", "content": "Refactor this Python class..."}],
                provider="anthropic",
            )
            print(rec["best_overall"]["model"])      # e.g. "claude-opus-4.6"
            print(rec["within_provider"]["model"])   # best Anthropic model
        """
        # 1. Classify + estimate complexity
        prompt_type = _classify_prompt(messages)
        text = _extract_text(messages)
        # ~4 chars per token is a common English heuristic
        est_tokens_in = max(10, len(text) // 4)
        # Assume output ~40% of input (conservative heuristic)
        est_tokens_out = max(10, est_tokens_in * 2 // 5)
        complexity = _score_complexity(messages, prompt_type, est_tokens_in)

        # 2. Score every registered model
        scored: list[dict] = []
        for model_id, info in _MODEL_REGISTRY.items():
            est_cost = _calc_cost(model_id, est_tokens_in, est_tokens_out)

            if budget_usd is not None and est_cost > budget_usd:
                continue

            # Use type-specific score if available, otherwise fall back to base quality
            type_score = info["type_scores"].get(prompt_type, info["quality"])

            # Penalise models that are under-powered for this complexity level
            complexity_gap = max(0, complexity - info["max_complexity"])
            penalty = complexity_gap * 0.12  # 12 % per level over the ceiling
            success_prob = max(0.0, min(1.0, (type_score / 10.0) - penalty))

            scored.append({
                "model": model_id,
                "provider": info["provider"],
                "quality_score": type_score,
                "estimated_tokens_in": est_tokens_in,
                "estimated_tokens_out": est_tokens_out,
                "estimated_cost_usd": round(est_cost, 8),
                "success_probability": round(success_prob, 3),
            })

        # Sort: best success_probability first, cheapest on tie
        scored.sort(key=lambda x: (-x["success_probability"], x["estimated_cost_usd"]))

        # 3. Pick best within provider (if requested)
        within_provider: dict | None = None
        if provider:
            prov_lower = provider.lower()
            within_provider = next(
                (m for m in scored if m["provider"] == prov_lower), None
            )

        return {
            "prompt_type": prompt_type,
            "complexity": complexity,
            "estimated_tokens_in": est_tokens_in,
            "within_provider": within_provider,
            "best_overall": scored[0] if scored else None,
        }
