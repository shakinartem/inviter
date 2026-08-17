from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CapacityAllocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=160)
    platform: str = Field(default="telegram", min_length=1, max_length=32)
    stage: Literal["engagement", "business"] = "business"
    event_type: str = Field(default="converted", min_length=1, max_length=64)
    horizon_hours: int = Field(default=168, ge=1, le=2160)
    total_capacity: int = Field(default=1000, ge=1, le=50000)
    allocation_mode: Literal["decision_grade", "coverage_expansion"] = "decision_grade"
    require_positive_conservative: bool = True


class CapacityAllocationPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    platform: str
    stage: str
    event_type: str
    horizon_hours: int
    total_capacity: int
    allocation_mode: str
    require_positive_conservative: bool
    status: str
    evidence_version: str
    offers_considered: int
    unique_candidates: int
    duplicate_offers_removed: int
    allocated_count: int
    unallocated_capacity: int
    expected_incremental_outcomes: float
    conservative_incremental_outcomes: float
    upside_incremental_outcomes: float
    replicated_context_coverage: float
    global_prior_status: str
    global_prior_lift: float
    global_prior_i_squared: float
    candidate_pool_capped: bool
    warnings: list[str] | None
    frozen_at: datetime
    created_at: datetime
    updated_at: datetime


class CapacityAllocationAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    segment_id: UUID
    audience_member_id: UUID
    allocation_rank: int
    segment_rank: int
    segment_name_snapshot: str
    activity_score: float | None
    intent_score: float | None
    readiness_score: float | None
    strongest_signal_type: str | None
    evidence_source: str
    context_key: str
    expected_incremental_probability: float
    conservative_incremental_probability: float
    upside_incremental_probability: float


class CapacityAllocationAssignmentListResponse(BaseModel):
    items: list[CapacityAllocationAssignmentResponse]
    total: int
    skip: int
    limit: int
