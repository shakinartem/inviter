"""add scheduled action jobs

Revision ID: 20260817_000002
Revises: 20260817_000001
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000002"
down_revision = "20260817_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target_external_user_id", sa.String(length=128), nullable=False),
        sa.Column("destination_external_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "audience_member_id",
            "action",
            name="uq_action_job_campaign_member_action",
        ),
    )
    op.create_index("ix_action_jobs_owner_id", "action_jobs", ["owner_id"], unique=False)
    op.create_index("ix_action_jobs_campaign_id", "action_jobs", ["campaign_id"], unique=False)
    op.create_index("ix_action_jobs_account_id", "action_jobs", ["account_id"], unique=False)
    op.create_index("ix_action_jobs_audience_member_id", "action_jobs", ["audience_member_id"], unique=False)
    op.create_index("ix_action_jobs_platform", "action_jobs", ["platform"], unique=False)
    op.create_index("ix_action_jobs_action", "action_jobs", ["action"], unique=False)
    op.create_index("ix_action_jobs_status", "action_jobs", ["status"], unique=False)
    op.create_index("ix_action_jobs_scheduled_at", "action_jobs", ["scheduled_at"], unique=False)
    op.create_index("ix_action_jobs_next_attempt_at", "action_jobs", ["next_attempt_at"], unique=False)
    op.create_index("ix_action_jobs_due", "action_jobs", ["status", "scheduled_at"], unique=False)
    op.create_index("ix_action_jobs_account_schedule", "action_jobs", ["account_id", "scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_action_jobs_account_schedule", table_name="action_jobs")
    op.drop_index("ix_action_jobs_due", table_name="action_jobs")
    op.drop_index("ix_action_jobs_next_attempt_at", table_name="action_jobs")
    op.drop_index("ix_action_jobs_scheduled_at", table_name="action_jobs")
    op.drop_index("ix_action_jobs_status", table_name="action_jobs")
    op.drop_index("ix_action_jobs_action", table_name="action_jobs")
    op.drop_index("ix_action_jobs_platform", table_name="action_jobs")
    op.drop_index("ix_action_jobs_audience_member_id", table_name="action_jobs")
    op.drop_index("ix_action_jobs_account_id", table_name="action_jobs")
    op.drop_index("ix_action_jobs_campaign_id", table_name="action_jobs")
    op.drop_index("ix_action_jobs_owner_id", table_name="action_jobs")
    op.drop_table("action_jobs")
