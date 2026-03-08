import asyncio
import json
import os
from datetime import datetime
from typing import List

from beanie import PydanticObjectId
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from auth import get_current_user
from database import get_db
from models import ApiCall
from schemas import ApiCallCreate, ApiCallOut, ApiCallSummary

_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 2.00, "output": 8.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "claude-opus-4.6": {"input": 5.00, "output": 25.00},
    "claude-opus-4.5": {"input": 5.00, "output": 25.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-haiku-4.5": {"input": 1.00, "output": 5.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-3-7-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-flash-latest": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-pro": {"input": 0.50, "output": 1.50},
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

router = APIRouter(prefix="/usage", tags=["usage"])

# In-memory queues for instant WebSocket push (one queue per connected user)
_live_queues: dict[str, asyncio.Queue] = {}


@router.post("/", response_model=ApiCallOut)
async def log_usage(record: ApiCallCreate, current_user: dict = Depends(get_current_user)):
    uid = PydanticObjectId(current_user["user_id"])
    data = record.model_dump()
    if not data.get("cost_usd"):
        data["cost_usd"] = _calc_cost(data["model"], data.get("tokens_in", 0), data.get("tokens_out", 0))
    doc = ApiCall(user_id=uid, **data)
    await doc.insert()
    out = _to_out(doc)
    # Instantly push to any open WebSocket for this user
    uid_str = str(uid)
    if uid_str in _live_queues:
        await _live_queues[uid_str].put(out)
    return out


@router.get("/", response_model=List[ApiCallOut])
async def get_usage(limit: int = 100, skip: int = 0, current_user: dict = Depends(get_current_user)):
    uid = PydanticObjectId(current_user["user_id"])
    docs = (
        await ApiCall.find(ApiCall.user_id == uid)
        .sort(-ApiCall.timestamp)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    stats_pipeline = [
        {"$match": {"user_id": ObjectId(current_user["user_id"]), "cost_usd": {"$gt": 0}}},
        {"$group": {
            "_id": None,
            "mean": {"$avg": "$cost_usd"},
            "std_dev": {"$stdDevPop": "$cost_usd"},
            "count": {"$sum": 1},
        }},
    ]
    stats_rows = await get_db()["api_calls"].aggregate(stats_pipeline).to_list(None)
    mean = std_dev = 0.0
    if stats_rows and stats_rows[0]["count"] >= 2:
        mean = stats_rows[0]["mean"]
        std_dev = stats_rows[0]["std_dev"] or 0.0

    def flag(cost: float) -> str | None:
        if std_dev == 0 or mean == 0:
            return None
        if cost < mean - std_dev:
            return "low"
        if cost > mean + std_dev:
            return "high"
        return "medium"

    return [_to_out(d, flag(d.cost_usd)) for d in docs]


@router.get("/summary", response_model=List[ApiCallSummary])
async def get_summary(current_user: dict = Depends(get_current_user)):
    uid = ObjectId(current_user["user_id"])
    pipeline = [
        {"$match": {"user_id": uid}},
        {
            "$group": {
                "_id": {"provider": "$provider", "model": "$model"},
                "total_tokens_in": {"$sum": "$tokens_in"},
                "total_tokens_out": {"$sum": "$tokens_out"},
                "total_cost_usd": {"$sum": "$cost_usd"},
                "request_count": {"$sum": 1},
            }
        },
    ]
    rows = await get_db()["api_calls"].aggregate(pipeline).to_list(None)
    return [
        ApiCallSummary(
            provider=r["_id"]["provider"],
            model=r["_id"]["model"],
            total_tokens_in=r["total_tokens_in"],
            total_tokens_out=r["total_tokens_out"],
            total_cost_usd=r["total_cost_usd"],
            request_count=r["request_count"],
        )
        for r in rows
    ]


@router.delete("/{record_id}")
async def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = await ApiCall.get(record_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=422, detail="Invalid record ID format")
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    if str(doc.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your record")
    await doc.delete()
    return {"ok": True}


@router.post("/recalculate-costs")
async def recalculate_costs(current_user: dict = Depends(get_current_user)):
    uid = PydanticObjectId(current_user["user_id"])
    docs = await ApiCall.find(ApiCall.user_id == uid, ApiCall.cost_usd == 0.0).to_list()
    updated = 0
    for doc in docs:
        cost = _calc_cost(doc.model, doc.tokens_in, doc.tokens_out)
        if cost > 0:
            doc.cost_usd = cost
            await doc.save()
            updated += 1
    return {"recalculated": updated}


@router.websocket("/ws/live")
async def live_usage(websocket: WebSocket, token: str):
    """Push new records instantly via in-process queue, with 30s keep-alive pings."""
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        uid = PydanticObjectId(payload["sub"])
    except (JWTError, Exception):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    uid_str = str(uid)
    queue: asyncio.Queue = asyncio.Queue()
    _live_queues[uid_str] = queue

    try:
        while True:
            try:
                out = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps([out.model_dump(mode="json")]))
            except asyncio.TimeoutError:
                await websocket.send_text("[]")  # keep-alive ping
    except WebSocketDisconnect:
        pass
    finally:
        _live_queues.pop(uid_str, None)


def _to_out(doc: ApiCall, cost_flag: str | None = None) -> ApiCallOut:
    return ApiCallOut(
        id=str(doc.id),
        user_id=str(doc.user_id),
        provider=doc.provider,
        model=doc.model,
        tokens_in=doc.tokens_in,
        tokens_out=doc.tokens_out,
        cost_usd=doc.cost_usd,
        latency_ms=doc.latency_ms,
        app_tag=doc.app_tag,
        key_hint=doc.key_hint,
        prompt_type=doc.prompt_type,
        complexity=doc.complexity,
        timestamp=doc.timestamp,
        cost_flag=cost_flag,
    )
