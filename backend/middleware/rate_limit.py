"""
Rate limit dependency — kept for backwards-compat.
The proxy router does its own quota enforcement via redis_client directly.
This module is a thin wrapper re-exported for any route that wants to
apply rate-limiting as a FastAPI dependency.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 1_000_000   # tokens per day
DEFAULT_WINDOW_MS = 86_400_000  # 24 h in ms


async def rate_limit_middleware(request: Request):
    """
    FastAPI dependency that enforces the daily token quota.
    Fail-open: if Redis is unavailable the request proceeds.
    """
    from redis_client import get_redis

    user = getattr(request.state, "user", None)
    if not user or "user_id" not in user:
        return None  # unauthenticated — JWT middleware handles rejection

    user_id = user["user_id"]

    try:
        r = await get_redis()
        if r is None:
            return None  # fail open

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{user_id}:{today}"
        used = await r.get(key)
        used = int(used) if used else 0

        if used >= DEFAULT_LIMIT:
            reset_epoch = int(
                datetime.now(timezone.utc)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
                + 86400
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

    return None
