from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommunityScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participants_count: int | None = Field(default=None, ge=0)
    active_1d: int | None = Field(default=None, ge=0)
    active_7d: int | None = Field(default=None, ge=0)
    messages_1d: int | None = Field(default=None, ge=0)
    messages_7d: int | None = Field(default=None, ge=0)
    unique_authors_1d: int | None = Field(default=None, ge=0)
    unique_authors_7d: int | None = Field(default=None, ge=0)
    relevance_score: float | None = Field(default=None, ge=0, le=100)
    growth_rate_30d: float | None = Field(default=None, ge=-1, le=10)
    bot_ratio: float | None = Field(default=None, ge=0, le=1)
    spam_ratio: float | None = Field(default=None, ge=0, le=1)


class CommunityScoreResponse(BaseModel):
    total_score: float
    activity_score: float
    relevance_score: float
    freshness_score: float
    audience_quality_score: float
    growth_score: float
    size_score: float
    penalty: float


class CommunityEnrichRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    member_limit: int = Field(default=2_000, ge=1, le=20_000)
    message_limit: int = Field(default=10_000, ge=1, le=50_000)
    lookback_days: int = Field(default=30, ge=1, le=30)
    relevance_score: float | None = Field(default=None, ge=0, le=100)


class CommunityEnrichResponse(BaseModel):
    community_id: UUID
    platform: str
    members_sampled: int
    messages_sampled: int
    audience_profiles: int
    active_1d: int
    active_7d: int
    messages_1d: int
    messages_7d: int
    quality_score: float
    snapshot_id: UUID
    captured_at: datetime


class AudienceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    external_user_id: str
    username: str | None
    first_name: str | None
    last_name: str | None
    is_bot: bool
    is_verified: bool
    is_scam: bool
    is_fake: bool
    is_blacklisted: bool
    last_activity_at: datetime | None
    activity_score: float | None
    relevance_score: float | None
    quality_score: float | None
    intent_score: float | None
    readiness_score: float | None
    created_at: datetime
    updated_at: datetime


class AudienceListResponse(BaseModel):
    items: list[AudienceMemberResponse]
    total: int
    skip: int
    limit: int
