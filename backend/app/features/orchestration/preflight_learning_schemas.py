from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PreflightDecisionHistoryItem(BaseModel):
    id: UUID
    campaign_id: UUID
    policy_version: str
    decision: str
    action_budget_requested: int
    action_budget_executable: int
    planned_jobs: int
    deadline_at: datetime
    required_daily_rate: int
    normal_daily_capacity: int
    emergency_daily_capacity: int
    n_minus_one_covers_required_rate: bool
    model_health_status: str
    active_calibrator_version: str | None
    tracked_jobs: int
    label_status: str
    actual_successful_jobs: int | None
    actual_failed_jobs: int | None
    actual_cancelled_jobs: int | None
    actual_completion_rate: float | None
    actual_met_execution_plan: bool | None
    launched_at: datetime
    label_finalized_at: datetime | None


class PreflightDecisionFinalizationResponse(BaseModel):
    examined: int
    labeled: int
    ineligible: int
    still_pending: int


class PreflightDecisionPerformanceRow(BaseModel):
    decision: str
    labeled_launches: int
    mean_completion_rate: float | None
    plan_success_rate: float | None
    mean_normal_daily_capacity: float | None
    n_minus_one_coverage_rate: float | None


class PreflightDecisionPerformanceResponse(BaseModel):
    policy_version: str
    labeled_launches: int
    ineligible_launches: int
    pending_mature_launches: int
    status: str
    warnings: list[str]
    by_decision: list[PreflightDecisionPerformanceRow]
