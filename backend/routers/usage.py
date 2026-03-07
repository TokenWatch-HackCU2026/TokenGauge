from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from database import get_db
from models import UsageRecord
from schemas import UsageRecordCreate, UsageRecordOut, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("/", response_model=UsageRecordOut)
def log_usage(record: UsageRecordCreate, db: Session = Depends(get_db)):
    db_record = UsageRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@router.get("/", response_model=List[UsageRecordOut])
def get_usage(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    return db.query(UsageRecord).order_by(UsageRecord.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/summary", response_model=List[UsageSummary])
def get_summary(db: Session = Depends(get_db)):
    rows = (
        db.query(
            UsageRecord.provider,
            UsageRecord.model,
            func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
            func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
            func.sum(UsageRecord.cost_usd).label("total_cost_usd"),
            func.count(UsageRecord.id).label("request_count"),
        )
        .group_by(UsageRecord.provider, UsageRecord.model)
        .all()
    )
    return [UsageSummary(**row._asdict()) for row in rows]


@router.delete("/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id).first()
    if record:
        db.delete(record)
        db.commit()
    return {"ok": True}
