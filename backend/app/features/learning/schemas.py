from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObservedOutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_job_id: UUID
    stage: Literal["engagement", "business"]
    event_type: str = Field(..., min_length=1, max_length=64)
    success: bool | None = True
    source: str = Field(default="manual", min_length=1, max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    value: float | None = None
    observed_at: datetime | None = None
    external_event_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=160)
    properties: dict[str, Any] | None = None


class OutcomeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    action_job_id: UUID | None
    campaign_id: UUID
    audience_member_id: UUID
    platform: str
    stage: str
    event_type: str
    success: bool | None
    source: str
    confidence: float
    value: float | None
    observed_at: datetime
    external_event_id: str | None
    properties: dict[str, Any] | None
    created_at: datetime


class OutcomeEventListResponse(BaseModel):
    items: list[OutcomeEventResponse]
    total: int
    skip: int
    limit: int


class LearningOverviewResponse(BaseModel):
    snapshots: int
    events_by_stage: dict[str, int]


class CalibrationRateRow(BaseModel):
    label: str
    samples: int
    positives: int
    rate: float
    confidence_low: float
    confidence_high: float


class CalibrationResponse(BaseModel):
    stage: str
    event_type: str
    horizon_hours: int
    bucket_size: int
    mature_samples: int
    positives: int
    observed_rate: float
    buckets: list[CalibrationRateRow]
    by_strongest_signal: list[CalibrationRateRow]
