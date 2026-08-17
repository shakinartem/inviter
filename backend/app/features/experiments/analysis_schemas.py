from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ExperimentArmResult(BaseModel):
    variant: Literal["treatment", "holdout"]
    units: int
    positives: int
    rate: float
    confidence_low: float
    confidence_high: float


class ExperimentBalanceMetric(BaseModel):
    metric: str
    treatment_mean: float | None
    holdout_mean: float | None
    standardized_difference: float | None


class CampaignCausalLiftResponse(BaseModel):
    experiment_id: UUID
    campaign_id: UUID
    campaign_title: str
    holdout_percentage: float
    stage: str
    event_type: str
    horizon_hours: int
    mature: bool
    hours_until_mature: float
    status: Literal["insufficient", "inconclusive", "positive", "negative"]
    treatment: ExperimentArmResult
    holdout: ExperimentArmResult
    lift_percentage_points: float
    confidence_low_percentage_points: float
    confidence_high_percentage_points: float
    relative_lift_percent: float | None
    incremental_outcomes_per_1000: float
    treatment_execution_rate: float
    treatment_transport_success_rate: float
    balance: list[ExperimentBalanceMetric]
    warnings: list[str]
