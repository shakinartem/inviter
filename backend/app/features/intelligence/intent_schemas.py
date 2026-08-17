from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntentScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    lookback_days: int = Field(default=30, ge=1, le=90)
    message_limit: int = Field(default=10_000, ge=1, le=50_000)
    minimum_score: float = Field(default=12.0, ge=0, le=100)


class IntentScanResponse(BaseModel):
    community_id: UUID
    platform: str
    messages_scanned: int
    candidate_signals: int
    signals_created: int
    members_scored: int
    strongest_signal: float
    average_member_intent: float
    signal_types: dict[str, int]
    model_version: str
    scanned_at: datetime


class IntentSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audience_member_id: UUID
    parsed_chat_id: UUID
    platform: str
    external_message_id: str | None
    observed_at: datetime
    signal_type: str
    topic: str | None
    score: float
    confidence: float
    model_version: str
    features: dict[str, Any] | None
    created_at: datetime
