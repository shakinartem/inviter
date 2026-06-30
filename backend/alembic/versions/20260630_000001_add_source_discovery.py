"""add source_candidates and source_scores tables

Revision ID: 20260630_000001
Revises: 20260629_000002
Create Date: 2026-06-30 23:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260630_000001"
down_revision: Union[str, None] = "20260629_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("username", sa.String(120), nullable=True, index=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("tgstat_url", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("subscribers_count", sa.Integer, nullable=True),
        sa.Column("avg_post_reach", sa.Integer, nullable=True),
        sa.Column("posts_per_day", sa.Integer, nullable=True),
        sa.Column("comments_enabled", sa.Boolean, nullable=True),
        sa.Column("linked_chat_url", sa.String(500), nullable=True),
        sa.Column("discovered_by_query", sa.String(255), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered", index=True),
        sa.Column("raw_data", postgresql.JSON, nullable=True),
    )

    op.create_table(
        "source_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("topic_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("activity_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("audience_quality_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chat_liveness_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reasons", postgresql.JSON, nullable=True),
    )

    op.create_index("ix_source_scores_candidate_id", "source_scores", ["source_candidate_id"])


def downgrade() -> None:
    op.drop_table("source_scores")
    op.drop_table("source_candidates")