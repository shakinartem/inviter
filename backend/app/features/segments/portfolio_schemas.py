from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PortfolioForecastRow(BaseModel):
    rank: int
    segment_id: UUID
    segment_name: str
    matched_count: int
    evaluated_members: int
    expected_outcomes: float
    conservative_outcomes: float
    upside_outcomes: float
    expected_rate: float
    conservative_rate: float
    quality_status: Literal["insufficient", "limited", "ready"]
    frozen_history_ratio: float
    contextual_coverage: float
    score: float
    warnings: list[str]


class OpportunityPortfolioResponse(BaseModel):
    stage: str
    event_type: str
    horizon_hours: int
    action_budget: int
    ranking_basis: str
    recommendation_segment_id: UUID | None
    recommendation_name: str | None
    warnings: list[str]
    rows: list[PortfolioForecastRow]
