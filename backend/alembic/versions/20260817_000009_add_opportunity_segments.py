"""add reusable opportunity segments and frozen campaign cohorts

Revision ID: 20260817_000009
Revises: 20260817_000008
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000009"
down_revision = "20260817_000008"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "audience_segments",
        *_base_columns(),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("criteria_version", sa.String(length=32), nullable=False, server_default=sa.text("'segment-v1'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_audience_segment_owner_name"),
    )
    op.create_index("ix_audience_segments_owner_id", "audience_segments", ["owner_id"])
    op.create_index("ix_audience_segments_platform", "audience_segments", ["platform"])
    op.create_index("ix_audience_segments_is_active", "audience_segments", ["is_active"])
    op.create_index("ix_audience_segments_last_refreshed_at", "audience_segments", ["last_refreshed_at"])
    op.create_index(
        "ix_audience_segments_owner_active",
        "audience_segments",
        ["owner_id", "is_active"],
    )

    op.create_table(
        "audience_segment_members",
        *_base_columns(),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("strongest_signal_type", sa.String(length=64), nullable=True),
        sa.Column("match_reasons", sa.JSON(), nullable=True),
        sa.Column("refresh_sequence", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["audience_segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment_id", "audience_member_id", name="uq_audience_segment_member"),
    )
    op.create_index("ix_audience_segment_members_segment_id", "audience_segment_members", ["segment_id"])
    op.create_index("ix_audience_segment_members_audience_member_id", "audience_segment_members", ["audience_member_id"])
    op.create_index("ix_audience_segment_members_matched_at", "audience_segment_members", ["matched_at"])
    op.create_index("ix_audience_segment_members_readiness_score", "audience_segment_members", ["readiness_score"])
    op.create_index(
        "ix_audience_segment_members_segment_readiness",
        "audience_segment_members",
        ["segment_id", "readiness_score"],
    )

    op.create_table(
        "campaign_audience_sources",
        *_base_columns(),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("criteria_snapshot", sa.JSON(), nullable=False),
        sa.Column("segment_refresh_sequence", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["audience_segments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", name="uq_campaign_audience_source_campaign"),
    )
    op.create_index("ix_campaign_audience_sources_owner_id", "campaign_audience_sources", ["owner_id"])
    op.create_index("ix_campaign_audience_sources_campaign_id", "campaign_audience_sources", ["campaign_id"])
    op.create_index("ix_campaign_audience_sources_segment_id", "campaign_audience_sources", ["segment_id"])

    op.create_table(
        "campaign_audience_members",
        *_base_columns(),
        sa.Column("campaign_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("strongest_signal_type", sa.String(length=64), nullable=True),
        sa.Column("match_reasons", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_source_id"], ["campaign_audience_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_source_id", "audience_member_id", name="uq_campaign_audience_member"),
    )
    op.create_index("ix_campaign_audience_members_campaign_source_id", "campaign_audience_members", ["campaign_source_id"])
    op.create_index("ix_campaign_audience_members_audience_member_id", "campaign_audience_members", ["audience_member_id"])
    op.create_index("ix_campaign_audience_members_readiness_score", "campaign_audience_members", ["readiness_score"])


def downgrade() -> None:
    op.drop_table("campaign_audience_members")
    op.drop_table("campaign_audience_sources")
    op.drop_table("audience_segment_members")
    op.drop_table("audience_segments")
