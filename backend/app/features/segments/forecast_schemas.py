from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class YieldEvidenceRow(BaseModel):
    label: str
    evidence_level: Literal["exact", "readiness", "signal", "global"]
    current_members: int
    historical_samples: int
    historical_positives: int
    observed_rate: float
    posterior_rate: float
    confidence_low: float
    confidence_high: float


class SegmentYieldForecastResponse(BaseModel):
    segment_id: UUID
    segment_name: str
    platform: str
    stage: str
    event_type: str
    horizon_hours: int
    requested_budget: int
    evaluated_members: int
    historical_samples: int
    historical_positives: int
    historical_observed_rate: float
    expected_outcomes: float
    expected_rate: float
    confidence_low_outcomes: float
    confidence_high_outcomes: float
    confidence_low_rate: float
    confidence_high_rate: float
    frozen_history_ratio: float
    evidence_coverage: dict[str, float]
    quality_status: Literal["insufficient", "limited", "ready"]
    warnings: list[str]
    evidence_rows: list[YieldEvidenceRow]
