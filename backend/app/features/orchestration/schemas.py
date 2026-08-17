from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampaignPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=1_000, ge=1, le=50_000)
    min_activity_score: float = Field(default=0.0, ge=0, le=100)
    min_readiness_score: float = Field(default=0.0, ge=0, le=100)
    account_ids: list[UUID] | None = None


class CampaignPlanResponse(BaseModel):
    campaign_id: UUID
    planned: int
    candidates: int
    accounts: int
    first_scheduled_at: datetime | None
    last_scheduled_at: datetime | None
    status: str | None = None
    experiment_id: UUID | None = None
    experiment_status: str | None = None
    action_budget: int | None = None
    candidate_pool_size: int | None = None
    treatment_count: int | None = None
    holdout_count: int | None = None


class ActionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    account_id: UUID
    audience_member_id: UUID
    platform: str
    action: str
    target_external_user_id: str
    destination_external_id: str
    status: str
    scheduled_at: datetime
    next_attempt_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    attempts: int
    max_attempts: int
    result_code: str | None
    result_message: str | None
    payload: dict | None
    created_at: datetime
    updated_at: datetime


class ActionJobListResponse(BaseModel):
    items: list[ActionJobResponse]
    total: int
    skip: int
    limit: int


class CampaignActionStatsResponse(BaseModel):
    campaign_id: UUID
    campaign_status: str
    total: int
    by_status: dict[str, int]
    success_rate: float