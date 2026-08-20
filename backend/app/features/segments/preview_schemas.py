from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.segments.schemas import SegmentCriteria


class SegmentPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(default="telegram", min_length=2, max_length=32)
    criteria: SegmentCriteria = Field(default_factory=SegmentCriteria)


class SegmentPreviewMember(BaseModel):
    audience_member_id: UUID
    username: str | None
    first_name: str | None
    last_name: str | None
    activity_score: float | None
    relevance_score: float | None
    intent_score: float | None
    readiness_score: float | None
    strongest_signal_type: str | None


class SegmentPreviewResponse(BaseModel):
    platform: str
    matched_count: int
    max_members: int
    average_activity_score: float | None
    average_relevance_score: float | None
    average_intent_score: float | None
    average_readiness_score: float | None
    strongest_signal_distribution: dict[str, int]
    community_count: int
    warnings: list[str]
    sample: list[SegmentPreviewMember]
