from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ContextualValueLiftRow(BaseModel):
    readiness_bucket: str
    strongest_signal_type: str
    experiments: int
    treatment_units: int
    holdout_units: int
    treatment_mean_value: float
    holdout_mean_value: float
    raw_incremental_value_per_unit: float
    shrunk_incremental_value_per_unit: float
    confidence_low_per_unit: float
    confidence_high_per_unit: float
    data_weight_percent: float
    incremental_value_per_1000: float
    evidence_status: Literal["exploratory", "replicated"]
    direction: Literal["positive", "negative", "inconclusive"]


class ContextualIncrementalBusinessValueResponse(BaseModel):
    event_type: str
    value_unit: str
    horizon_hours: int
    aggregation: Literal["sum", "max"]
    global_prior_value_per_unit: float
    global_prior_status: str
    global_prior_i_squared_percent: float
    strata_evaluated: int
    strata_replicated: int
    warnings: list[str]
    rows: list[ContextualValueLiftRow]
