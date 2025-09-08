# =============================================
# File: app/db/models.py
# Purpose: SQLModel ORM definitions for persisted analytics: user query events (including OOS flag and latency) and recommendation logs.
# =============================================

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class QueryEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    text: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    oos: bool = False
    latency_ms: int = 0

class Recommendation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    item_id: str
    why: str
    ts: datetime = Field(default_factory=datetime.utcnow)
