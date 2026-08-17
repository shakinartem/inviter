from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ExperimentValueLiftRow(BaseModel):
    experiment_id: UUID
    campaign_id: UUID
    campaign_title: str
    treatment_units: int
    holdout_units: int
    treatment_mean_value: float
    holdout_mean_value: float
    incremental_value_per_unit: float
    standard_error: float
    weight_percent: float


class IncrementalBusinessValueResponse(BaseModel):
    event_type: str
    value_unit: str
    horizon_hours: int
    aggregation: Literal["sum", "max"]
    experiments_considered: int
    experiments_included: int
    randomized_units: int
    pooled_incremental_value_per_unit: float
    confidence_low_per_unit: float
    confidence_high_per_unit: float
    incremental_value_per_1000: float
    tau_squared: float
    i_squared_percent: float
    status: Literal["insufficient", "positive", "negative", "inconclusive", "heterogeneous"]
    warnings: list[str]
    rows: list[ExperimentValueLiftRow]
