from datetime import datetime, timezone
from typing import Literal, Optional

import pymongo
from beanie import Document
from pydantic import EmailStr, Field
from beanie import PydanticObjectId


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Document):
    email: EmailStr
    password_hash: Optional[str] = None  # None for Google OAuth-only users

    # Profile
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

    # Google OAuth
    google_id: Optional[str] = None
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None

    # JWT refresh token invalidation
    refresh_token_hash: Optional[str] = None

    # SDK token (persistent, 1 year)
    sdk_token: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "users"
        indexes = [
            pymongo.IndexModel([("email", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel(
                [("google_id", pymongo.ASCENDING)],
                unique=True,
                partialFilterExpression={"google_id": {"$type": "string"}},
            ),
        ]



class ApiCall(Document):
    user_id: PydanticObjectId
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    app_tag: Optional[str] = None
    complexity: Optional[int] = None
    prompt_type: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "api_calls"
        indexes = [
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)]
            ),
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("provider", pymongo.ASCENDING)]
            ),
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("model", pymongo.ASCENDING)]
            ),
        ]



class Alert(Document):
    user_id: PydanticObjectId
    type: Literal["limit", "spike"]
    threshold: float
    triggered_at: Optional[datetime] = None
    acknowledged: bool = False

    class Settings:
        name = "alerts"


class SpikeEvent(Document):
    user_id: PydanticObjectId
    detected_at: datetime = Field(default_factory=_utcnow)
    baseline_tokens: int
    actual_tokens: int
    multiplier: float

    class Settings:
        name = "spike_events"
