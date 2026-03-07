"""
redis/rate_limiter.py
---------------------
Sliding window rate limiter backed by a Redis sorted set.

Uses an atomic Lua script so the check-and-increment is a single
round-trip with no race conditions.

Key: ratelimit:{userId}  (sorted set, members scored by timestamp ms)

Returns:
    {
        "allowed": bool,
        "remaining": int,      # requests left in current window
        "reset_at": int,       # unix ms when the oldest entry expires
    }
"""

import time

import aioredis

# ---------------------------------------------------------------------------
# Lua script — executed atomically on the Redis server.
#
# KEYS[1]  : the sorted-set key  (e.g. "ratelimit:user123")
# ARGV[1]  : now_ms             (current unix timestamp in milliseconds)
# ARGV[2]  : window_ms          (sliding window size in milliseconds)
# ARGV[3]  : limit              (max requests allowed in the window)
#
# Returns: [allowed (0|1), current_count, window_end_ms]
# ---------------------------------------------------------------------------
_RATE_LIMIT_LUA = """
local key          = KEYS[1]
local now          = tonumber(ARGV[1])
local window       = tonumber(ARGV[2])
local limit        = tonumber(ARGV[3])
local window_start = now - window

-- 1. Evict entries older than the sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- 2. Count remaining entries
local count = redis.call('ZCARD', key)

-- 3. Reject if at or over limit
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_at = oldest[2] and (tonumber(oldest[2]) + window) or (now + window)
    return {0, count, reset_at}
end

-- 4. Record this request (unique member = timestamp + random suffix)
local member = now .. ':' .. math.random(1000000)
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)

return {1, count + 1, now + window}
"""

# Default limits — callers can override per-request
DEFAULT_WINDOW_MS: int = 60_000   # 1 minute
DEFAULT_LIMIT: int = 100          # 100 requests per minute


async def check_rate_limit(
    redis: aioredis.Redis,
    user_id: str,
    limit: int = DEFAULT_LIMIT,
    window_ms: int = DEFAULT_WINDOW_MS,
) -> dict:
    """
    Check and record a rate-limit hit for user_id.

    Args:
        redis:     Active aioredis client.
        user_id:   The user to rate-limit.
        limit:     Max requests allowed in the window.
        window_ms: Sliding window size in milliseconds.

    Returns:
        {
            "allowed":   bool  — False means the request should be rejected (HTTP 429),
            "remaining": int   — Requests still allowed in the current window,
            "reset_at":  int   — Unix ms timestamp when the window resets,
        }
    """
    now_ms = int(time.time() * 1000)
    key = f"ratelimit:{user_id}"

    result = await redis.eval(_RATE_LIMIT_LUA, 1, key, now_ms, window_ms, limit)

    allowed = int(result[0]) == 1
    count = int(result[1])
    reset_at = int(result[2])

    return {
        "allowed": allowed,
        "remaining": max(0, limit - count),
        "reset_at": reset_at,
    }
