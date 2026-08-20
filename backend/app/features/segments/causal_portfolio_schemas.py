from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CausalPortfolioRow(BaseModel):
    rank: int
    segment_id: UUID
    segment_name: str
    matched_count: int
    evaluated_members: int
    expected_incremental_outcomes: float
    conservative_incremental_outcomes: float
    upside_incremental_outcomes: float
    expected_incremental_rate: float
    conservative_incremental_rate: float
    replicated_context_coverage: float
    exploratory_context_coverage: float
    global_fallback_coverage: float
    evidence_status: Literal["insufficient", "limited", "ready"]
    warnings: list[str]


class CausalOpportunityPortfolioResponse(BaseModel):
    stage: str
    event_type: str
    horizon_hours: int
    action_budget: int
    global_prior_status: str
    global_prior_lift_percentage_points: float
    global_prior_i_squared_percent: float
    recommendation_segment_id: UUID | None
    recommendation_name: str | None
    ranking_basis: str
    warnings: list[str]
    rows: list[CausalPortfolioRow]
