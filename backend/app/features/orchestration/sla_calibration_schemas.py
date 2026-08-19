from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SLAFinalizationResponse(BaseModel):
    examined: int
    labeled: int
    ineligible_queue: int
    intervened: int
    still_pending: int


class SLACalibrationBucket(BaseModel):
    lower_bound: float
    upper_bound: float
    samples: int
    mean_prediction: float | None
    observed_completion_rate: float | None
    brier_score: float | None


class SLACalibrationResponse(BaseModel):
    model_version: str
    campaign_id: UUID | None
    labeled_samples: int
    ineligible_samples: int
    intervened_samples: int
    pending_mature_samples: int
    mean_prediction: float | None
    observed_completion_rate: float | None
    calibration_bias: float | None
    brier_score: float | None
    expected_calibration_error: float | None
    status: str
    warnings: list[str]
    buckets: list[SLACalibrationBucket]


class SLAContinuityCalibrationBucket(BaseModel):
    lower_bound: float
    upper_bound: float
    samples: int
    mean_prediction: float | None
    observed_continuity_rate: float | None
    brier_score: float | None


class SLAContinuityCalibrationResponse(BaseModel):
    model_version: str
    campaign_id: UUID | None
    labeled_samples: int
    ineligible_samples: int
    intervened_samples: int
    pending_mature_samples: int
    mean_prediction: float | None
    observed_continuity_rate: float | None
    calibration_bias: float | None
    brier_score: float | None
    expected_calibration_error: float | None
    status: str
    warnings: list[str]
    buckets: list[SLAContinuityCalibrationBucket]


class SLALabelAuditItem(BaseModel):
    id: UUID
    campaign_id: UUID
    remaining_actions: int
    forecast_created_at: datetime
    deadline_at: datetime
    predicted_completion_probability: float | None
    predicted_continuity_probability: float | None
    label_status: str
    queue_eligible_at_forecast: bool | None
    actual_successful_actions: int | None
    actual_hard_failure_days: int | None
    actual_met_sla: bool | None
    actual_met_continuity: bool | None
    actual_continuity_rate: float | None
    continuity_windows_total: int | None
    continuity_windows_met: int | None
    actual_completed_at: datetime | None
    label_finalized_at: datetime | None
