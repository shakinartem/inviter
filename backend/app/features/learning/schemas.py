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


class FeedbackOutcomeLabel(BaseModel):
    stage: str
    event_type: str
    success: bool | None
    source: str
    observed_at: datetime


class FeedbackActionResponse(BaseModel):
    action_job_id: UUID
    campaign_id: UUID
    campaign_title: str
    audience_member_id: UUID
    person: str
    username: str | None
    platform: str
    action: str
    job_status: str
    result_code: str | None
    attempts: int
    executed_at: datetime | None
    activity_score: float | None
    intent_score: float | None
    readiness_score: float | None
    strongest_signal_type: str | None
    outcomes: list[FeedbackOutcomeLabel]


class FeedbackActionListResponse(BaseModel):
    items: list[FeedbackActionResponse]
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


class ObserverCursorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    platform: str
    status: str
    last_observed_at: datetime | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    messages_seen: int
    outcomes_created: int
    run_count: int


class ObserverScanResponse(BaseModel):
    campaign_id: UUID
    platform: str | None = None
    since: datetime | None = None
    messages_seen: int = 0
    outcomes_created: int = 0
    last_observed_at: datetime | None = None
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
