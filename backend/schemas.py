from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# --- Auth schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    org_id: Optional[int] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime


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
