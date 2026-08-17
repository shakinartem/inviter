"""add outcome learning feature snapshots and events

Revision ID: 20260817_000008
Revises: 20260817_000007
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000008"
down_revision = "20260817_000007"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "action_feature_snapshots",
        *_timestamps(),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_transport_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("strongest_signal_type", sa.String(length=64), nullable=True),
        sa.Column("intent_model_versions", sa.JSON(), nullable=True),
        sa.Column("feature_payload", sa.JSON(), nullable=True),
        sa.Column("snapshot_version", sa.String(length=64), nullable=False, server_default=sa.text("'action-feature-v1'")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_job_id"], ["action_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_job_id", name="uq_action_feature_snapshot_job"),
    )
    op.create_index("ix_action_feature_snapshots_owner_id", "action_feature_snapshots", ["owner_id"])
    op.create_index("ix_action_feature_snapshots_campaign_id", "action_feature_snapshots", ["campaign_id"])
    op.create_index("ix_action_feature_snapshots_audience_member_id", "action_feature_snapshots", ["audience_member_id"])
    op.create_index("ix_action_feature_snapshots_captured_at", "action_feature_snapshots", ["captured_at"])
    op.create_index("ix_action_feature_snapshots_readiness_score", "action_feature_snapshots", ["readiness_score"])
    op.create_index(
        "ix_action_feature_snapshots_owner_captured",
        "action_feature_snapshots",
        ["owner_id", "captured_at"],
    )

    op.create_table(
        "outcome_events",
        *_timestamps(),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_event_id", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_job_id"], ["action_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "dedupe_key", name="uq_outcome_event_owner_dedupe"),
    )
    op.create_index("ix_outcome_events_owner_id", "outcome_events", ["owner_id"])
    op.create_index("ix_outcome_events_action_job_id", "outcome_events", ["action_job_id"])
    op.create_index("ix_outcome_events_campaign_id", "outcome_events", ["campaign_id"])
    op.create_index("ix_outcome_events_audience_member_id", "outcome_events", ["audience_member_id"])
    op.create_index("ix_outcome_events_stage", "outcome_events", ["stage"])
    op.create_index("ix_outcome_events_event_type", "outcome_events", ["event_type"])
    op.create_index("ix_outcome_events_observed_at", "outcome_events", ["observed_at"])
    op.create_index(
        "ix_outcome_events_stage_type",
        "outcome_events",
        ["stage", "event_type"],
    )
    op.create_index(
        "ix_outcome_events_member_observed",
        "outcome_events",
        ["audience_member_id", "observed_at"],
    )
    op.create_index(
        "ix_outcome_events_campaign_stage",
        "outcome_events",
        ["campaign_id", "stage"],
    )


def downgrade() -> None:
    op.drop_table("outcome_events")
    op.drop_table("action_feature_snapshots")
