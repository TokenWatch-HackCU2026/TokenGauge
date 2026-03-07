from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UsageRecordCreate(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    project: Optional[str] = None


class UsageRecordOut(UsageRecordCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UsageSummary(BaseModel):
    provider: str
    model: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    request_count: int
