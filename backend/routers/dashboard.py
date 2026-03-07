import time
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import get_current_user
from database import get_db
from redis_client import cache_get, cache_set, make_cache_key

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEFAULT_WINDOW_DAYS = 7
QUOTA_LIMIT = 1_000_000
QUOTA_WINDOW_MS = 24 * 60 * 60 * 1000


# ── Response models ────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    request_count: int
    avg_latency_ms: float


class TimeseriesPoint(BaseModel):
    date: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    request_count: int


class BreakdownRow(BaseModel):
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    request_count: int


class QuotaOut(BaseModel):
    limit: int
    used: int
    remaining: int
    reset_at: int   # unix ms
    window_ms: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_range() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=DEFAULT_WINDOW_DAYS), now


def _build_match(
    user_id: ObjectId,
    start: datetime,
    end: datetime,
    provider: str | None = None,
    model: str | None = None,
    app_tag: str | None = None,
) -> dict:
    match: dict = {"user_id": user_id, "timestamp": {"$gte": start, "$lte": end}}
    if provider:
        match["provider"] = provider
    if model:
        match["model"] = model
    if app_tag:
        match["app_tag"] = app_tag
    return match


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=SummaryOut)
async def get_summary(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    provider: Optional[str] = None,
    model: Optional[str] = None,
    app_tag: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    uid = ObjectId(current_user["user_id"])
    start, end = (start_date, end_date) if start_date and end_date else _default_range()
    ck = make_cache_key(current_user["user_id"], "summary", str(start), str(end), provider or "", model or "", app_tag or "")

    if cached := await cache_get(ck):
        return SummaryOut(**cached)

    pipeline = [
        {"$match": _build_match(uid, start, end, provider, model, app_tag)},
        {"$group": {
            "_id": None,
            "total_tokens_in": {"$sum": "$tokens_in"},
            "total_tokens_out": {"$sum": "$tokens_out"},
            "total_cost_usd": {"$sum": "$cost_usd"},
            "request_count": {"$sum": 1},
            "avg_latency_ms": {"$avg": "$latency_ms"},
        }},
    ]
    rows = await get_db()["api_calls"].aggregate(pipeline).to_list(None)
    if not rows:
        result = SummaryOut(total_tokens_in=0, total_tokens_out=0, total_cost_usd=0.0, request_count=0, avg_latency_ms=0.0)
    else:
        r = rows[0]
        result = SummaryOut(
            total_tokens_in=r["total_tokens_in"],
            total_tokens_out=r["total_tokens_out"],
            total_cost_usd=r["total_cost_usd"],
            request_count=r["request_count"],
            avg_latency_ms=round(r.get("avg_latency_ms") or 0, 1),
        )

    await cache_set(ck, result.model_dump(), ttl=60)
    return result


@router.get("/timeseries", response_model=List[TimeseriesPoint])
async def get_timeseries(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    group_by: Literal["hour", "day"] = "day",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    uid = ObjectId(current_user["user_id"])
    start, end = (start_date, end_date) if start_date and end_date else _default_range()
    ck = make_cache_key(current_user["user_id"], "timeseries", str(start), str(end), group_by, provider or "", model or "")

    if cached := await cache_get(ck):
        return [TimeseriesPoint(**p) for p in cached]

    date_fmt = "%Y-%m-%dT%H:00:00Z" if group_by == "hour" else "%Y-%m-%d"
    pipeline = [
        {"$match": _build_match(uid, start, end, provider, model)},
        {"$group": {
            "_id": {"$dateToString": {"format": date_fmt, "date": "$timestamp"}},
            "tokens_in": {"$sum": "$tokens_in"},
            "tokens_out": {"$sum": "$tokens_out"},
            "cost_usd": {"$sum": "$cost_usd"},
            "request_count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    rows = await get_db()["api_calls"].aggregate(pipeline).to_list(None)
    result = [
        TimeseriesPoint(date=r["_id"], tokens_in=r["tokens_in"], tokens_out=r["tokens_out"], cost_usd=r["cost_usd"], request_count=r["request_count"])
        for r in rows
    ]

    await cache_set(ck, [p.model_dump() for p in result], ttl=60)
    return result


@router.get("/breakdown", response_model=List[BreakdownRow])
async def get_breakdown(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    uid = ObjectId(current_user["user_id"])
    start, end = (start_date, end_date) if start_date and end_date else _default_range()
    ck = make_cache_key(current_user["user_id"], "breakdown", str(start), str(end))

    if cached := await cache_get(ck):
        return [BreakdownRow(**r) for r in cached]

    pipeline = [
        {"$match": _build_match(uid, start, end)},
        {"$group": {
            "_id": {"provider": "$provider", "model": "$model"},
            "tokens_in": {"$sum": "$tokens_in"},
            "tokens_out": {"$sum": "$tokens_out"},
            "cost_usd": {"$sum": "$cost_usd"},
            "request_count": {"$sum": 1},
        }},
        {"$sort": {"cost_usd": -1}},
    ]
    rows = await get_db()["api_calls"].aggregate(pipeline).to_list(None)
    result = [
        BreakdownRow(provider=r["_id"]["provider"], model=r["_id"]["model"], tokens_in=r["tokens_in"], tokens_out=r["tokens_out"], cost_usd=r["cost_usd"], request_count=r["request_count"])
        for r in rows
    ]

    await cache_set(ck, [b.model_dump() for b in result], ttl=60)
    return result


@router.get("/quota", response_model=QuotaOut)
async def get_quota(current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    now_ms = int(time.time() * 1000)
    used = 0

    try:
        from redis_client import get_redis
        r = await get_redis()
        if r:
            key = f"ratelimit:{uid}"
            window_start = now_ms - QUOTA_WINDOW_MS
            await r.zremrangebyscore(key, "-inf", window_start)
            used = await r.zcard(key)
    except Exception:
        pass

    return QuotaOut(
        limit=QUOTA_LIMIT,
        used=used,
        remaining=max(0, QUOTA_LIMIT - used),
        reset_at=now_ms + QUOTA_WINDOW_MS,
        window_ms=QUOTA_WINDOW_MS,
    )
