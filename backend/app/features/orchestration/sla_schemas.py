from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionSLAForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    remaining_actions: int = Field(..., ge=1, le=1_000_000)
    deadline_days: int = Field(default=7, ge=1, le=90)
    target_sla: float = Field(default=0.90, ge=0.50, le=0.999)
    lookback_days: int = Field(default=60, ge=14, le=180)
    reserve_percentages: list[float] | None = None
    simulations: int = Field(default=3000, ge=500, le=10000)
    persist_snapshot: bool = True

    @field_validator("reserve_percentages")
    @classmethod
    def validate_reserves(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("reserve_percentages cannot be empty")
        normalized = sorted({round(float(item), 2) for item in value})
        if any(item < 0 or item > 50 for item in normalized):
            raise ValueError("reserve percentages must be between 0 and 50")
        if len(normalized) > 21:
            raise ValueError("at most 21 reserve scenarios are allowed")
        return normalized


class AccountHazardResponse(BaseModel):
    account_id: UUID
    label: str
    health_score: float
    emergency_daily_capacity: int
    exposure_days: int
    hard_failure_days: int
    posterior_daily_hazard: float
    conservative_daily_hazard: float
    evidence_quality: str


class SLAScenarioResponse(BaseModel):
    reserve_percentage: float
    normal_daily_capacity: int
    emergency_daily_capacity: int
    reserved_headroom: int
    nominal_completion_days: float | None
    modelled_completion_probability: float
    conservative_completion_probability: float
    expected_actions_by_deadline: float
    conservative_expected_actions_by_deadline: float
    meets_target_sla: bool
    throughput_penalty_vs_zero_reserve: int


class ExecutionSLAForecastResponse(BaseModel):
    forecast_id: UUID | None
    model_version: str
    campaign_id: UUID
    campaign_title: str
    remaining_actions: int
    deadline_days: int
    deadline_at: datetime
    target_sla: float
    lookback_days: int
    simulations: int
    evidence_quality: str
    total_exposure_days: int
    total_hard_failure_days: int
    current_reserve_percentage: float
    current_scenario: SLAScenarioResponse
    recommended_scenario: SLAScenarioResponse | None
    status: str
    warnings: list[str]
    accounts: list[AccountHazardResponse]
    scenarios: list[SLAScenarioResponse]


class ExecutionSLAForecastHistoryItem(BaseModel):
    id: UUID
    campaign_id: UUID
    model_version: str
    remaining_actions: int
    deadline_at: datetime
    target_sla: float
    evidence_quality: str
    current_reserve_percentage: float
    recommended_reserve_percentage: float | None
    recommended_conservative_probability: float | None
    normal_daily_capacity: int
    emergency_daily_capacity: int
    actual_completed_at: datetime | None
    actual_met_sla: bool | None
    created_at: datetime
