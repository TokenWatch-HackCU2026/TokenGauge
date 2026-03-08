"""
AI Gateway / Proxy  —  FR-1

Routes:
    POST /proxy/{provider}/{path:path}

The proxy:
1. Authenticates the caller via JWT
2. Enforces per-user daily token quota (Redis)
3. Decrypts the user's provider API key (KMS / Fernet)
4. Classifies the prompt (complexity + type)
5. Forwards the request to the provider
6. Parses tokens + calculates cost
7. Logs to MongoDB api_calls (fire-and-forget)
8. Returns the provider response unmodified

Supported providers:  anthropic | openai | google | mistral
"""

import asyncio
import logging
import time
import uuid
from typing import Any

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from auth import get_current_user
from classifier import classify_prompt
from database import get_db
from models import ApiCall
from routers.keys import get_decrypted_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy", tags=["proxy"])

# ── Provider configuration ────────────────────────────────────────────────────

PROVIDER_CONFIG: dict[str, dict] = {
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "auth_header": "x-api-key",
        "auth_prefix": "",
        "extra_headers": {"anthropic-version": "2023-06-01"},
        "auth_via": "header",
    },
    "openai": {
        "base_url": "https://api.openai.com",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "extra_headers": {},
        "auth_via": "header",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com",
        "auth_via": "query_param",   # ?key={api_key}
        "auth_header": "",
        "auth_prefix": "",
        "extra_headers": {},
    },
    "mistral": {
        "base_url": "https://api.mistral.ai",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "extra_headers": {},
        "auth_via": "header",
    },
}

# ── Pricing table (USD per 1M tokens) ────────────────────────────────────────

PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-3-haiku":          {"input": 0.25,  "output": 1.25},
    "claude-3-5-haiku":        {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet":       {"input": 3.00,  "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus":           {"input": 15.00, "output": 75.00},
    "claude-opus-4":           {"input": 15.00, "output": 75.00},
    # OpenAI
    "gpt-4o-mini":             {"input": 0.15,  "output": 0.60},
    "gpt-4o":                  {"input": 5.00,  "output": 15.00},
    "gpt-4-turbo":             {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":           {"input": 0.50,  "output": 1.50},
    # Google
    "gemini-1.5-flash":        {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":          {"input": 3.50,  "output": 10.50},
    "gemini-2.0-flash":        {"input": 0.10,  "output": 0.40},
    # Mistral
    "mistral-small":           {"input": 1.00,  "output": 3.00},
    "mistral-medium":          {"input": 2.70,  "output": 8.10},
    "mistral-large":           {"input": 8.00,  "output": 24.00},
    "mistral-small-latest":    {"input": 1.00,  "output": 3.00},
    "mistral-large-latest":    {"input": 8.00,  "output": 24.00},
}

DAILY_TOKEN_QUOTA = 1_000_000  # tokens per day per user


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def _check_quota(user_id: str, tokens_needed: int = 0) -> None:
    """
    Fail-open: if Redis is unavailable the request goes through.
    Raises HTTP 429 if the user has exceeded their daily token quota.
    """
    try:
        from redis_client import get_redis
        r = await get_redis()
        if r is None:
            return  # fail open

        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{user_id}:{today}"

        used = await r.get(key)
        used = int(used) if used else 0

        if used >= DAILY_TOKEN_QUOTA:
            reset_epoch = int(
                (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                 .timestamp()) + 86400
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily token quota exceeded. Resets at midnight UTC.",
                headers={"Retry-After": str(reset_epoch)},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Rate limit check failed (fail-open): %s", exc)


async def _increment_quota(user_id: str, tokens: int) -> None:
    """Increment the daily token counter after a successful request."""
    try:
        from redis_client import get_redis
        r = await get_redis()
        if r is None:
            return
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{user_id}:{today}"
        await r.incrby(key, tokens)
        await r.expire(key, 172800)  # 2-day TTL
    except Exception as exc:
        logger.warning("Failed to increment quota counter: %s", exc)


# ── Token extraction ──────────────────────────────────────────────────────────

def _extract_model_from_body(provider: str, body: dict) -> str:
    return body.get("model", "unknown")


def _extract_tokens(provider: str, body: dict, resp_json: dict) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from the provider response."""
    try:
        if provider == "anthropic":
            u = resp_json.get("usage", {})
            return u.get("input_tokens", 0), u.get("output_tokens", 0)

        elif provider in ("openai", "mistral"):
            u = resp_json.get("usage", {})
            return u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

        elif provider == "google":
            u = resp_json.get("usageMetadata", {})
            return u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)

    except Exception:
        pass
    return 0, 0


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    # Try exact match, then prefix match
    price = PRICING.get(model)
    if price is None:
        for key, val in PRICING.items():
            if model.startswith(key) or key.startswith(model):
                price = val
                break
    if price is None:
        return 0.0
    return (tokens_in / 1_000_000) * price["input"] + (tokens_out / 1_000_000) * price["output"]


# ── Log to MongoDB (fire-and-forget) ──────────────────────────────────────────

async def _log_call(
    user_id: str,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    app_tag: str | None,
    complexity: int | None,
    prompt_type: str | None,
) -> None:
    try:
        uid = ObjectId(user_id)
        doc = ApiCall(
            user_id=uid,
            provider=provider,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            app_tag=app_tag,
            complexity=complexity,
            prompt_type=prompt_type,
        )
        await doc.insert()
    except Exception as exc:
        logger.error("Failed to log API call: %s", exc)


# ── Main proxy handler ────────────────────────────────────────────────────────

@router.api_route("/{provider}/{path:path}", methods=["POST", "GET", "PUT", "DELETE", "PATCH"])
async def proxy_request(
    provider: str,
    path: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    provider = provider.lower()
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Supported: {', '.join(PROVIDER_CONFIG)}",
        )

    cfg = PROVIDER_CONFIG[provider]
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    app_tag = request.headers.get("X-App-Tag")

    # 1. Read & parse request body
    raw_body = await request.body()
    body: dict[str, Any] = {}
    try:
        import json
        body = json.loads(raw_body) if raw_body else {}
    except Exception:
        pass

    # 2. Classify prompt
    classification: dict[str, Any] = {"complexity": None, "prompt_type": None}
    try:
        messages = body.get("messages") or body.get("contents") or []
        if messages:
            classification = classify_prompt(messages)
    except Exception:
        pass

    # 3. Quota check
    await _check_quota(user_id)

    # 4. Decrypt provider API key
    raw_key = await get_decrypted_key(user_id, provider, request_id)

    # 5. Build forwarded request headers
    # Strip hop-by-hop and auth headers; add provider auth
    skip_headers = {"authorization", "host", "content-length", "transfer-encoding", "connection"}
    fwd_headers: dict[str, str] = {
        k: v for k, v in request.headers.items()
        if k.lower() not in skip_headers
    }
    fwd_headers.update(cfg.get("extra_headers", {}))

    if cfg["auth_via"] == "header":
        fwd_headers[cfg["auth_header"]] = cfg["auth_prefix"] + raw_key

    # 6. Build target URL
    target_url = f"{cfg['base_url']}/{path}"
    params = dict(request.query_params)
    if cfg["auth_via"] == "query_param":
        params["key"] = raw_key

    # 7. Forward
    start_ms = int(time.time() * 1000)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                params=params,
                content=raw_body,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Provider request timed out")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Provider unreachable: {exc}")

    latency_ms = int(time.time() * 1000) - start_ms

    # 8. Clear the raw key from local scope
    raw_key = ""

    # 9. Parse response for token counts
    model = _extract_model_from_body(provider, body)
    tokens_in, tokens_out = 0, 0
    resp_json: dict = {}
    if resp.headers.get("content-type", "").startswith("application/json"):
        try:
            resp_json = resp.json()
            # Provider may return the model name in the response
            model = resp_json.get("model", model)
            tokens_in, tokens_out = _extract_tokens(provider, body, resp_json)
        except Exception:
            pass

    cost_usd = _calculate_cost(model, tokens_in, tokens_out)

    # 10. Fire-and-forget logging + quota increment
    asyncio.create_task(_log_call(
        user_id=user_id,
        provider=provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        app_tag=app_tag,
        complexity=classification.get("complexity"),
        prompt_type=classification.get("prompt_type"),
    ))
    if tokens_in + tokens_out > 0:
        asyncio.create_task(_increment_quota(user_id, tokens_in + tokens_out))

    # 11. Return provider response
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={
            k: v for k, v in resp.headers.items()
            if k.lower() not in ("transfer-encoding", "content-encoding", "connection")
        },
        media_type=resp.headers.get("content-type"),
    )
