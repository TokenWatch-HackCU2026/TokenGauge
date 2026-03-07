from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# --- ApiCall ---

class ApiCallCreate(BaseModel):
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    app_tag: Optional[str] = None


class ApiCallOut(ApiCallCreate):
    id: str
    user_id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ApiCallSummary(BaseModel):
    provider: str
    model: str
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    request_count: int


# --- Auth ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    org_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
