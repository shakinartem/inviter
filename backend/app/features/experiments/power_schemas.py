from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ExperimentPowerPlanResponse(BaseModel):
    segment_id: UUID
    segment_name: str
    platform: str
    stage: str
    event_type: str
    horizon_hours: int
    holdout_percentage: float
    alpha: float
    target_power: float
    baseline_rate: float | None
    baseline_source: Literal["mature_holdout_history", "explicit_assumption", "missing"]
    baseline_samples: int
    baseline_positives: int
    target_lift_percentage_points: float
    required_total_units: int | None
    required_treatment_units: int | None
    required_holdout_units: int | None
    available_segment_units: int
    requested_action_budget: int
    projected_total_units: int
    projected_treatment_units: int
    projected_holdout_units: int
    projected_mde_percentage_points: float | None
    adequately_powered: bool
    status: Literal["baseline_required", "underpowered", "adequately_powered", "impossible"]
    warnings: list[str]
