from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MetaExperimentRow(BaseModel):
    experiment_id: UUID
    campaign_id: UUID
    campaign_title: str
    treatment_units: int
    treatment_positives: int
    holdout_units: int
    holdout_positives: int
    lift_percentage_points: float
    standard_error_percentage_points: float
    weight_percent: float


class IncrementalYieldMetaResponse(BaseModel):
    stage: str
    event_type: str
    horizon_hours: int
    experiments_considered: int
    experiments_included: int
    randomized_units: int
    unique_people: int
    repeated_people: int
    pooled_lift_percentage_points: float
    confidence_low_percentage_points: float
    confidence_high_percentage_points: float
    incremental_outcomes_per_1000: float
    tau_squared: float
    i_squared_percent: float
    q_statistic: float
    status: Literal["insufficient", "positive", "negative", "inconclusive", "heterogeneous"]
    warnings: list[str]
    rows: list[MetaExperimentRow]
