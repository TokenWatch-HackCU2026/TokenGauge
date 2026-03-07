import sys
from pathlib import Path

# Ensure the root directory (where the `redis` folder lives) is in sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import Request, HTTPException, status
from redis.client import get_redis
from redis.rate_limiter import check_rate_limit, DEFAULT_LIMIT, DEFAULT_WINDOW_MS


async def rate_limit_middleware(request: Request):
    """
    Dependency or middleware function to enforce rate limiting on specific routes.
    Extracts the user ID from the request state (set by the auth middleware)
    and checks if they have exceeded their quota.

    Usage as a dependency:
        from middleware.rate_limit import rate_limit_middleware
        from fastapi import Depends

        @router.post("/proxy/...")
        async def proxy_endpoint(
            request: Request,
            _=Depends(rate_limit_middleware)
        ):
            ...
    """
    # Assuming user_id is injected into request.state.user by the auth middleware (Partner 1)
    user = getattr(request.state, "user", None)
    if not user or "user_id" not in user:
        # If there's no auth, we can't rate limit by user.
        # Fallback to rate limiting by IP, or just allow it if auth is mandatory elsewhere.
        client_ip = request.client.host if request.client else "unknown"
        user_id = f"ip_{client_ip}"
    else:
        user_id = user["user_id"]

    try:
        redis = get_redis()
        # TODO: Lookup user's specific tier limits from DB if needed
        limit_result = await check_rate_limit(redis, user_id=user_id)

        if not limit_result["allowed"]:
            reset_at_s = limit_result["reset_at"] // 1000
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "Retry-After": str(reset_at_s),
                    "X-RateLimit-Remaining": str(limit_result["remaining"]),
                },
            )

        # Optional: Add remaining capacity headers to the response afterwards, 
        # but since this is a dependency pre-request, we only block here.
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        # If Redis is unavailable, NFR-R2 says: fail open (allow request) with alert
        import logging
        logging.getLogger(__name__).warning("Active rate limiting bypassed due to Redis error: %s", exc)

    return None
