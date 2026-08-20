from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceHealthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: Literal["incremental_outcomes", "incremental_business_value"] = "incremental_outcomes"
    stage: Literal["engagement", "business"] = "business"
    event_type: str = Field(default="converted", min_length=1, max_length=64)
    value_unit: str | None = Field(default=None, min_length=1, max_length=16)
    value_aggregation: Literal["sum", "max"] | None = None
    horizon_hours: int = Field(default=168, ge=1, le=2160)
    recent_window_days: int = Field(default=45, ge=7, le=365)
    max_evidence_age_days: int = Field(default=120, ge=14, le=730)

    @model_validator(mode="after")
    def validate_objective(self) -> "EvidenceHealthRequest":
        if self.objective == "incremental_business_value":
            if self.stage != "business":
                raise ValueError("business-value evidence health requires stage=business")
            if not self.value_unit:
                raise ValueError("value_unit is required for business-value evidence health")
            self.value_unit = self.value_unit.strip().upper()
            self.value_aggregation = self.value_aggregation or "sum"
        else:
            self.value_unit = None
            self.value_aggregation = None
        return self


class EvidenceWindowEstimate(BaseModel):
    experiments: int
    estimate: float | None
    confidence_low: float | None
    confidence_high: float | None
    i_squared_percent: float | None


class EvidenceHealthResponse(BaseModel):
    objective: str
    event_type: str
    value_unit: str | None
    horizon_hours: int
    recent_window_days: int
    max_evidence_age_days: int
    latest_mature_assignment_at: datetime | None
    evidence_age_days: float | None
    recent: EvidenceWindowEstimate
    historical: EvidenceWindowEstimate
    drift_difference: float | None
    drift_confidence_low: float | None
    drift_confidence_high: float | None
    drift_z_score: float | None
    status: Literal["insufficient", "stable", "watch", "drift_positive", "drift_negative", "stale"]
    recommend_reexperiment: bool
    warnings: list[str]
