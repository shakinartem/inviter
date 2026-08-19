from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SLACalibratorBin(BaseModel):
    lower_bound: float
    upper_bound: float
    samples: int
    mean_raw_prediction: float
    observed_rate: float | None
    calibrated_probability: float


class SLACalibratorResponse(BaseModel):
    id: UUID
    base_model_version: str
    calibrator_version: str
    status: str
    sample_count: int
    train_count: int
    test_count: int
    training_cutoff_at: datetime
    raw_brier_test: float
    calibrated_brier_test: float
    raw_ece_test: float
    calibrated_ece_test: float
    raw_bias_test: float
    calibrated_bias_test: float
    activation_eligible: bool
    mapping: list[SLACalibratorBin]
    trained_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


class SLACalibratorTrainRequest(BaseModel):
    base_model_version: str = Field(default="execution-sla-v1", min_length=1, max_length=64)
    min_samples: int = Field(default=100, ge=100, le=10000)
    test_fraction: float = Field(default=0.20, ge=0.15, le=0.40)
    prior_strength: float = Field(default=8.0, ge=1.0, le=50.0)


class SLACalibratorTrainResponse(BaseModel):
    status: str
    eligible_samples: int
    minimum_required: int
    calibrator: SLACalibratorResponse | None
    warnings: list[str]


class SLACalibratorApplyResponse(BaseModel):
    calibrator_version: str | None
    raw_probability: float
    calibrated_probability: float
