from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AdaptiveExecutionRequest(BaseModel):
    source_account_id: UUID
    campaign_id: UUID | None = None
    max_jobs: int = Field(default=500, ge=1, le=2000)
    reason: str = Field(default="manual_rebalance", min_length=1, max_length=64)


class AdaptiveMoveResponse(BaseModel):
    job_id: UUID
    campaign_id: UUID
    from_account_id: UUID
    from_account_label: str
    to_account_id: UUID
    to_account_label: str
    previous_scheduled_at: datetime
    new_scheduled_at: datetime
    reason: str
    target_health_score: float
    target_daily_capacity: int


class AdaptivePlanResponse(BaseModel):
    source_account_id: UUID
    source_account_label: str
    reason: str
    movable_jobs: int
    moved_jobs: int
    untouched_started_or_retry_jobs: int
    no_safe_target_jobs: int
    target_accounts: int
    latest_reassigned_at: datetime | None
    moves: list[AdaptiveMoveResponse]


class AdaptiveAssignmentEventResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    action_job_id: UUID
    from_account_id: UUID
    to_account_id: UUID
    reason: str
    policy_version: str
    previous_scheduled_at: datetime
    new_scheduled_at: datetime
    details: dict | None
    created_at: datetime


class AdaptivePolicyResponse(BaseModel):
    policy_version: Literal["adaptive-execution-v1"] = "adaptive-execution-v1"
    movable_statuses: list[str] = ["planned"]
    attempts_must_equal: int = 0
    target_pool_rule: str = "existing_campaign_account_pool_only"
    scheduling_rule: str = "never_earlier_than_original_and_never_above_risk_adjusted_capacity"
    retry_rule: str = "started_or_retry_jobs_stay_pinned_to_original_account"
