from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampaignPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_budget: int = Field(default=1_000, ge=1, le=50_000)
    deadline_days: int = Field(default=7, ge=1, le=90)
    min_activity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    min_readiness_score: float = Field(default=0.0, ge=0.0, le=100.0)
    account_ids: list[UUID] | None = None


class CampaignPreflightCheck(BaseModel):
    key: str
    status: str
    blocking: bool
    title: str
    message: str
    details: dict | None = None


class CampaignPreflightAccount(BaseModel):
    account_id: UUID
    label: str
    health_score: float
    risk_score: float
    emergency_daily_capacity: int
    normal_daily_capacity: int
    queued_jobs: int
    reasons: list[str]


class CampaignPreflightResponse(BaseModel):
    campaign_id: UUID
    campaign_title: str
    decision: str
    action_budget_requested: int
    action_budget_executable: int
    deadline_days: int
    required_daily_rate: int
    platform: str | None
    destination_title: str | None
    destination_ready: bool
    frozen_cohort_size: int
    eligible_candidate_pool: int
    required_candidate_pool: int
    holdout_percentage: float
    estimated_treatment_candidates: int
    eligible_accounts: int
    quarantined_accounts: int
    recommended_account_ids: list[UUID]
    normal_daily_capacity: int
    emergency_daily_capacity: int
    reserved_failover_headroom: int
    estimated_completion_days: float | None
    n_minus_one_surviving_capacity: int
    n_minus_one_covers_required_rate: bool
    model_health_status: str
    active_calibrator_version: str | None
    checks: list[CampaignPreflightCheck]
    accounts: list[CampaignPreflightAccount]
    warnings: list[str]
