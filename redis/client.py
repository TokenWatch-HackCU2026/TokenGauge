"""
redis/client.py
---------------
aioredis connection singleton for TokenWatch.

Usage (FastAPI lifespan):
    from redis.client import connect_redis, disconnect_redis, get_redis

Usage (dependency injection):
    from redis.client import get_redis
    from fastapi import Depends
    import aioredis

    @router.get("/example")
    async def example(redis: aioredis.Redis = Depends(get_redis)):
        ...
"""

import logging
import os

import aioredis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

_redis: aioredis.Redis | None = None


async def connect_redis() -> None:
    """Create the global Redis connection pool. Call once at app startup."""
    global _redis
    _redis = await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connectivity
    await _redis.ping()
    logger.info("Connected to Redis at %s", REDIS_URL)


async def disconnect_redis() -> None:
    """Close the global Redis connection pool. Call once at app shutdown."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Disconnected from Redis")


def get_redis() -> aioredis.Redis:
    """
    FastAPI dependency — returns the active Redis client.

    Raises RuntimeError if called before connect_redis().
    """
    if _redis is None:
        raise RuntimeError("Redis is not connected. Call connect_redis() first.")
    return _redis


async def redis_health_check() -> dict:
    """
    Returns a health status dict suitable for inclusion in /health endpoint.
    """
    try:
        client = get_redis()
        pong = await client.ping()
        return {"redis": "ok" if pong else "degraded"}
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {"redis": "unavailable"}
