from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SegmentCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_activity_score: float | None = Field(default=None, ge=0, le=100)
    min_relevance_score: float | None = Field(default=None, ge=0, le=100)
    min_quality_score: float | None = Field(default=None, ge=0, le=100)
    min_intent_score: float | None = Field(default=None, ge=0, le=100)
    min_readiness_score: float | None = Field(default=None, ge=0, le=100)
    last_activity_days: int | None = Field(default=None, ge=1, le=3650)
    community_ids: list[UUID] = Field(default_factory=list, max_length=100)
    signal_types: list[str] = Field(default_factory=list, max_length=50)
    signal_lookback_days: int = Field(default=90, ge=1, le=3650)
    min_communities: int | None = Field(default=None, ge=1, le=100)
    include_bots: bool = False
    max_members: int = Field(default=10_000, ge=1, le=50_000)
    sort_by: Literal["readiness", "intent", "activity"] = "readiness"

    @field_validator("signal_types")
    @classmethod
    def normalize_signal_types(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip().lower().replace(" ", "_")
            if item and item not in normalized:
                normalized.append(item)
        return normalized


class SegmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    platform: str = Field(default="telegram", min_length=2, max_length=32)
    criteria: SegmentCriteria = Field(default_factory=SegmentCriteria)


class SegmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    criteria: SegmentCriteria | None = None
    is_active: bool | None = None


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    platform: str
    criteria: dict
    criteria_version: str
    is_active: bool
    matched_count: int
    last_refreshed_at: datetime | None
    refresh_count: int
    created_at: datetime
    updated_at: datetime


class SegmentRefreshResponse(BaseModel):
    segment_id: UUID
    matched_count: int
    refresh_sequence: int
    refreshed_at: datetime


class SegmentMemberResponse(BaseModel):
    segment_member_id: UUID
    audience_member_id: UUID
    platform: str
    username: str | None
    first_name: str | None
    last_name: str | None
    activity_score: float | None
    relevance_score: float | None
    intent_score: float | None
    readiness_score: float | None
    strongest_signal_type: str | None
    matched_at: datetime
    match_reasons: dict | None


class SegmentMemberListResponse(BaseModel):
    items: list[SegmentMemberResponse]
    total: int
    skip: int
    limit: int


class CampaignAudienceSourceResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    segment_id: UUID
    frozen_at: datetime
    member_count: int
    segment_refresh_sequence: int
    criteria_snapshot: dict
