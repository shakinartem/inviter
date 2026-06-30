"""
Pydantic schemas for Source Discovery module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==================== Search ====================


class SourceDiscoverySearchRequest(BaseModel):
    """Request to search sources on TGStat."""
    query: str = Field(..., min_length=1, max_length=200, description="Keyword search query")
    limit: int = Field(default=20, ge=1, le=100, description="Max results")
    category: Optional[str] = Field(default=None, max_length=100, description="TGStat category filter")
    language: Optional[str] = Field(default=None, max_length=10, description="Language filter")


# ==================== Source Candidate ====================


class SourceCandidateListItem(BaseModel):
    """Short source candidate info for lists."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: str
    title: Optional[str]
    username: Optional[str]
    url: Optional[str]
    tgstat_url: Optional[str]
    category: Optional[str]
    subscribers_count: Optional[int]
    status: str
    total_score: Optional[int] = Field(default=None, description="Best score if analyzed")
    discovered_by_query: Optional[str]
    discovered_at: Optional[datetime]
    created_at: datetime


class SourceCandidateResponse(BaseModel):
    """Full source candidate info."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    source_type: str
    title: Optional[str]
    username: Optional[str]
    url: Optional[str]
    tgstat_url: Optional[str]
    category: Optional[str]
    description: Optional[str]
    subscribers_count: Optional[int]
    avg_post_reach: Optional[int]
    posts_per_day: Optional[float]
    comments_enabled: Optional[bool]
    linked_chat_url: Optional[str]
    discovered_by_query: Optional[str]
    discovered_at: Optional[datetime]
    last_analyzed_at: Optional[datetime]
    status: str
    raw_data: Optional[dict[str, Any]]
    scores: list[SourceScoreResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SourceCandidateListResponse(BaseModel):
    """Paginated list of source candidates."""
    items: list[SourceCandidateListItem]
    total: int
    skip: int = 0
    limit: int = 50


# ==================== Source Score ====================


class SourceScoreResponse(BaseModel):
    """Analysis score for a source."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_candidate_id: UUID
    topic_score: int
    activity_score: int
    audience_quality_score: int
    chat_liveness_score: int
    total_score: int
    reasons: Optional[dict[str, Any]]
    created_at: datetime


class ScoreDetail(BaseModel):
    """Scoring detail for frontend display."""
    topic_score: int
    activity_score: int
    audience_quality_score: int
    chat_liveness_score: int
    total_score: int
    reasons: list[str]
    recommendation: str = Field(
        description="good source / weak source / dead / likely inflated"
    )


# ==================== Analysis ====================


class AnalysisResult(BaseModel):
    """Result of source analysis with scores."""
    candidate: SourceCandidateResponse
    score: SourceScoreResponse


class SelectResult(BaseModel):
    """Result of selecting a source."""
    candidate_id: UUID
    status: str = "selected"
    message: str