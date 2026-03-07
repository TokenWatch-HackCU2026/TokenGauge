from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from database import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, index=True)       # e.g. "openai", "anthropic"
    model = Column(String, index=True)          # e.g. "gpt-4o", "claude-3-5-sonnet"
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    project = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
