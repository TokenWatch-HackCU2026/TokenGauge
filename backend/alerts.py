"""
alerts.py
---------
Check token usage against quota thresholds and enqueue SMS alerts.
Called after each API call is logged.
"""

import logging
import os
from datetime import datetime, timezone

from beanie import PydanticObjectId

from models import Alert, User
from redis_client import get_redis

logger = logging.getLogger(__name__)

QUOTA_LIMIT = 1_000_000  # tokens per day
THRESHOLDS = [
    (0.80, "quota_80"),
    (1.00, "quota_100"),
]


async def check_quota_alerts(user_id: str) -> None:
    """
    After a usage event, check if the user has crossed 80% or 100%
    of their daily quota and send an SMS if they haven't been alerted yet.
    """
    r = await get_redis()
    if r is None:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quota_key = f"quota:{user_id}:{today}"
    raw = await r.get(quota_key)
    used = int(raw) if raw else 0

    for ratio, alert_type in THRESHOLDS:
        threshold = int(QUOTA_LIMIT * ratio)
        if used < threshold:
            continue

        # Deduplicate: only alert once per threshold per day
        dedup_key = f"alert_sent:{user_id}:{alert_type}:{today}"
        already_sent = await r.get(dedup_key)
        if already_sent:
            continue

        # Look up user's phone number
        user = await User.get(PydanticObjectId(user_id))
        if not user or not user.phone:
            logger.info("No phone number for user %s — skipping %s alert", user_id, alert_type)
            continue

        # Build message
        pct = int(ratio * 100)
        remaining = max(0, QUOTA_LIMIT - used)
        if alert_type == "quota_100":
            body = (
                f"TokenGauge Alert: You've hit 100% of your daily token quota "
                f"({QUOTA_LIMIT:,} tokens). API calls will be rate-limited until "
                f"your quota resets at midnight UTC."
            )
        else:
            body = (
                f"TokenGauge Alert: You've used {pct}% of your daily token quota. "
                f"{remaining:,} tokens remaining out of {QUOTA_LIMIT:,}."
            )

        # Enqueue the SMS job via arq
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            pool = await create_pool(RedisSettings.from_dsn(redis_url))
            await pool.enqueue_job(
                "send_sms_alert",
                user_id,
                user.phone,
                alert_type,
                body,
            )
            await pool.close()
            logger.info("Enqueued %s SMS alert for user %s", alert_type, user_id)
        except Exception as exc:
            logger.error("Failed to enqueue SMS alert: %s", exc)
            continue

        # Mark as sent for today (expires in 24h)
        await r.setex(dedup_key, 86400, "1")

        # Persist alert record in MongoDB
        alert = Alert(
            user_id=PydanticObjectId(user_id),
            type="limit",
            threshold=ratio,
            triggered_at=datetime.now(timezone.utc),
        )
        await alert.insert()
