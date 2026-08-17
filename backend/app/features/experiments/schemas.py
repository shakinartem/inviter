from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CampaignExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    holdout_percentage: float
    status: str
    action_budget: int | None
    candidate_pool_size: int
    treatment_count: int
    holdout_count: int
    assigned_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExperimentAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    campaign_id: UUID
    audience_member_id: UUID
    variant: Literal["treatment", "holdout"]
    rank: int
    assigned_at: datetime


class ExperimentAssignmentListResponse(BaseModel):
    items: list[ExperimentAssignmentResponse]
    total: int
    skip: int
    limit: int
