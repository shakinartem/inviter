"""add campaign execution events

Revision ID: 20260819_000023
Revises: 20260819_000022
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000023"
down_revision = "20260819_000022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_execution_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_execution_events_owner_id", "campaign_execution_events", ["owner_id"])
    op.create_index("ix_campaign_execution_events_campaign_id", "campaign_execution_events", ["campaign_id"])
    op.create_index("ix_campaign_execution_events_event_type", "campaign_execution_events", ["event_type"])
    op.create_index("ix_campaign_execution_events_actor_type", "campaign_execution_events", ["actor_type"])
    op.create_index("ix_campaign_execution_events_actor_user_id", "campaign_execution_events", ["actor_user_id"])
    op.create_index("ix_campaign_execution_events_occurred_at", "campaign_execution_events", ["occurred_at"])
    op.create_index("ix_campaign_execution_events_campaign_time", "campaign_execution_events", ["campaign_id", "occurred_at"])
    op.create_index("ix_campaign_execution_events_owner_time", "campaign_execution_events", ["owner_id", "occurred_at"])
    op.create_index("ix_campaign_execution_events_campaign_type_time", "campaign_execution_events", ["campaign_id", "event_type", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_campaign_execution_events_campaign_type_time", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_owner_time", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_campaign_time", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_occurred_at", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_actor_user_id", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_actor_type", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_event_type", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_campaign_id", table_name="campaign_execution_events")
    op.drop_index("ix_campaign_execution_events_owner_id", table_name="campaign_execution_events")
    op.drop_table("campaign_execution_events")
