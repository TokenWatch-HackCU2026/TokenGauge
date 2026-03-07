from typing import List

from beanie import PydanticObjectId
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from models import ApiCall
from schemas import ApiCallCreate, ApiCallOut, ApiCallSummary

router = APIRouter(prefix="/usage", tags=["usage"])

# Placeholder user id used until auth is wired up
_DEV_USER_ID = PydanticObjectId("000000000000000000000001")
_DEV_USER_ID_RAW = ObjectId("000000000000000000000001")


@router.post("/", response_model=ApiCallOut)
async def log_usage(record: ApiCallCreate):
    doc = ApiCall(user_id=_DEV_USER_ID, **record.model_dump())
    await doc.insert()
    return _to_out(doc)


@router.get("/", response_model=List[ApiCallOut])
async def get_usage(limit: int = 100, skip: int = 0):
    docs = (
        await ApiCall.find(ApiCall.user_id == _DEV_USER_ID)
        .sort(-ApiCall.timestamp)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    return [_to_out(d) for d in docs]


@router.get("/summary", response_model=List[ApiCallSummary])
async def get_summary():
    pipeline = [
        {"$match": {"user_id": _DEV_USER_ID_RAW}},
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
    rows = await ApiCall.aggregate(pipeline).to_list()
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
async def delete_record(record_id: str):
    try:
        doc = await ApiCall.get(record_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=422, detail="Invalid record ID format")
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    await doc.delete()
    return {"ok": True}


def _to_out(doc: ApiCall) -> ApiCallOut:
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
        timestamp=doc.timestamp,
    )
