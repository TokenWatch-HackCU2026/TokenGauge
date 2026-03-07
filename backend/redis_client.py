import hashlib
import json
import logging
import os
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is not None:
        return _redis
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        client = aioredis.from_url(url, decode_responses=True)
        await client.ping()
        _redis = client
        logger.info("Connected to Redis at %s", url)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — caching disabled", exc)
    return _redis


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def make_cache_key(*parts: str) -> str:
    raw = ":".join(parts)
    return "dashboard:" + hashlib.md5(raw.encode()).hexdigest()
