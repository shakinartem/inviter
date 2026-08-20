from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ContextualLiftRow(BaseModel):
    readiness_bucket: str
    strongest_signal_type: str
    experiments: int
    treatment_units: int
    treatment_positives: int
    holdout_units: int
    holdout_positives: int
    raw_lift_percentage_points: float
    shrunk_lift_percentage_points: float
    confidence_low_percentage_points: float
    confidence_high_percentage_points: float
    data_weight_percent: float
    incremental_outcomes_per_1000: float
    evidence_status: Literal["exploratory", "replicated"]
    direction: Literal["positive", "negative", "inconclusive"]


class ContextualIncrementalYieldResponse(BaseModel):
    stage: str
    event_type: str
    horizon_hours: int
    global_prior_lift_percentage_points: float
    global_prior_status: str
    global_prior_i_squared_percent: float
    strata_evaluated: int
    strata_replicated: int
    warnings: list[str]
    rows: list[ContextualLiftRow]
