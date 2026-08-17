from __future__ import annotations

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
