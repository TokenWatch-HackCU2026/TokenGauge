from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, validator
import re


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @validator("email")
    def validate_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError("Invalid email format")
        return v
    @validator('password')
    def validate_password(cls, value):
        """
        Password rules:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        """
        if len(value) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', value):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', value):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', value):
            raise ValueError('Password must contain at least one number')
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# --- ApiCall ---

class ApiCallCreate(BaseModel):
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    app_tag: Optional[str] = None
    key_hint: Optional[str] = None
    prompt_type: Optional[str] = None
    complexity: Optional[int] = None
    timestamp: Optional[datetime] = None


class ApiCallOut(ApiCallCreate):
    id: str
    user_id: str
    prompt_type: Optional[str] = None
    complexity: Optional[int] = None
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
