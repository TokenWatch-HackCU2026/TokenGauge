"""
redis/cache.py
--------------
Dashboard query result cache backed by Redis strings.

Key pattern: dashboard:{userId}:{queryHash}
TTL:         60 seconds (invalidated immediately after a proxy call)

Usage:
    from redis.cache import get_cached, set_cached, invalidate_user_cache

    # In a dashboard endpoint:
    cached = await get_cached(redis, user_id, query_params)
    if cached:
        return cached

    result = await expensive_aggregation(...)
    await set_cached(redis, user_id, query_params, result)
    return result

    # After a proxy request writes a new api_call:
    await invalidate_user_cache(redis, user_id)
"""

import hashlib
import json
import logging

import aioredis

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS: int = 60  # dashboard cache TTL


def _cache_key(user_id: str, query_params: dict) -> str:
    """
    Build a deterministic cache key from user_id and an arbitrary dict of
    query parameters (e.g. date range, provider filter, group-by).
    """
    stable = json.dumps(query_params, sort_keys=True)
    query_hash = hashlib.sha256(stable.encode()).hexdigest()[:16]
    return f"dashboard:{user_id}:{query_hash}"


async def get_cached(
    redis: aioredis.Redis,
    user_id: str,
    query_params: dict,
) -> list | dict | None:
    """
    Return the cached result for this user + query, or None on a cache miss.
    """
    key = _cache_key(user_id, query_params)
    raw = await redis.get(key)
    if raw is None:
        logger.debug("Cache miss: %s", key)
        return None
    logger.debug("Cache hit: %s", key)
    return json.loads(raw)


async def set_cached(
    redis: aioredis.Redis,
    user_id: str,
    query_params: dict,
    value: list | dict,
    ttl: int = CACHE_TTL_SECONDS,
) -> None:
    """
    Store a query result in the cache for `ttl` seconds.
    """
    key = _cache_key(user_id, query_params)
    await redis.set(key, json.dumps(value), ex=ttl)
    logger.debug("Cached result under %s (TTL=%ds)", key, ttl)


async def invalidate_user_cache(
    redis: aioredis.Redis,
    user_id: str,
) -> int:
    """
    Delete all dashboard cache entries for a user.
    Called after every successful proxy request to keep the dashboard fresh.

    Returns the number of keys deleted.
    """
    pattern = f"dashboard:{user_id}:*"
    keys = await redis.keys(pattern)
    if keys:
        deleted = await redis.delete(*keys)
        logger.debug("Invalidated %d cache key(s) for user %s", deleted, user_id)
        return deleted
    return 0
