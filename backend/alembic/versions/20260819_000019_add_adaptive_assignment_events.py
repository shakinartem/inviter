"""add adaptive execution assignment audit

Revision ID: 20260819_000019
Revises: 20260818_000018
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000019"
down_revision = "20260818_000018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_assignment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("previous_scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_job_id"], ["action_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_assignment_events_owner_id", "action_assignment_events", ["owner_id"])
    op.create_index("ix_action_assignment_events_campaign_id", "action_assignment_events", ["campaign_id"])
    op.create_index("ix_action_assignment_events_action_job_id", "action_assignment_events", ["action_job_id"])
    op.create_index("ix_action_assignment_events_from_account_id", "action_assignment_events", ["from_account_id"])
    op.create_index("ix_action_assignment_events_to_account_id", "action_assignment_events", ["to_account_id"])
    op.create_index("ix_action_assignment_events_reason", "action_assignment_events", ["reason"])
    op.create_index(
        "ix_action_assignment_events_job_created",
        "action_assignment_events",
        ["action_job_id", "created_at"],
    )
    op.create_index(
        "ix_action_assignment_events_owner_created",
        "action_assignment_events",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_action_assignment_events_campaign_created",
        "action_assignment_events",
        ["campaign_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_assignment_events_campaign_created", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_owner_created", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_job_created", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_reason", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_to_account_id", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_from_account_id", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_action_job_id", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_campaign_id", table_name="action_assignment_events")
    op.drop_index("ix_action_assignment_events_owner_id", table_name="action_assignment_events")
    op.drop_table("action_assignment_events")
