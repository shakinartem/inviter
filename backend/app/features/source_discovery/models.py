"""
Models for Source Discovery - TGStat keyword discovery and source analysis.

SourceCandidate: discovered Telegram channel/chat from TGStat search
SourceScore: analysis scores for a source candidate
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


SOURCE_CANDIDATE_STATUSES: tuple[str, ...] = (
    "discovered", "analyzed", "selected", "rejected", "error",
)

SOURCE_TYPES: tuple[str, ...] = (
    "channel", "chat", "group", "unknown",
)


class SourceCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Discovered Telegram source candidate from TGStat search."""

    __tablename__ = "source_candidates"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        doc="channel/chat/group/unknown",
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Channel/chat title",
    )
    username: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
        doc="Telegram @username (without @)",
    )
    url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Telegram URL (t.me/...)",
    )
    tgstat_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="TGStat page URL",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="TGStat category",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Channel description",
    )
    subscribers_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of subscribers",
    )
    avg_post_reach: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Average post reach (views)",
    )
    posts_per_day: Mapped[float | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Posts per day (approximate)",
    )
    comments_enabled: Mapped[bool | None] = mapped_column(
        default=None,
        nullable=True,
        doc="Whether comments/discussion is enabled",
    )
    linked_chat_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Linked discussion chat URL",
    )
    discovered_by_query: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Search query that discovered this source",
    )
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="When this source was discovered",
    )
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When this source was last analyzed",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="discovered",
        index=True,
        doc="discovered/analyzed/selected/rejected/error",
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Raw TGStat page data",
    )

    owner = relationship("User", back_populates="source_candidates", lazy="selectin")
    scores: Mapped[list["SourceScore"]] = relationship(
        back_populates="source_candidate",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def display_name(self) -> str:
        return self.title or self.username or self.url or f"Source {self.id}"

    def __repr__(self) -> str:
        return (
            f"<SourceCandidate id={self.id} title={self.title!r} "
            f"type={self.source_type} status={self.status}>"
        )


class SourceScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Analysis scores for a source candidate."""

    __tablename__ = "source_scores"

    source_candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("source_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Topic relevance score 0-100",
    )
    activity_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Activity/liveness score 0-100",
    )
    audience_quality_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Audience quality score 0-100",
    )
    chat_liveness_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Chat/discussion liveness score 0-100",
    )
    total_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Weighted total score 0-100",
    )
    reasons: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="List of scoring reasons",
    )

    source_candidate: Mapped["SourceCandidate"] = relationship(
        back_populates="scores",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<SourceScore id={self.id} candidate={self.source_candidate_id} "
            f"total={self.total_score}>"
        )