"""add preflight decision learning snapshots

Revision ID: 20260819_000026
Revises: 20260819_000025
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000026"
down_revision = "20260819_000025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_preflight_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("action_budget_requested", sa.Integer(), nullable=False),
        sa.Column("action_budget_executable", sa.Integer(), nullable=False),
        sa.Column("planned_jobs", sa.Integer(), nullable=False),
        sa.Column("deadline_days", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_daily_rate", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("destination_ready", sa.Boolean(), nullable=False),
        sa.Column("frozen_cohort_size", sa.Integer(), nullable=False),
        sa.Column("eligible_candidate_pool", sa.Integer(), nullable=False),
        sa.Column("required_candidate_pool", sa.Integer(), nullable=False),
        sa.Column("holdout_percentage", sa.Float(), nullable=False),
        sa.Column("eligible_accounts", sa.Integer(), nullable=False),
        sa.Column("quarantined_accounts", sa.Integer(), nullable=False),
        sa.Column("normal_daily_capacity", sa.Integer(), nullable=False),
        sa.Column("emergency_daily_capacity", sa.Integer(), nullable=False),
        sa.Column("reserved_failover_headroom", sa.Integer(), nullable=False),
        sa.Column("n_minus_one_surviving_capacity", sa.Integer(), nullable=False),
        sa.Column("n_minus_one_covers_required_rate", sa.Boolean(), nullable=False),
        sa.Column("model_health_status", sa.String(length=32), nullable=False),
        sa.Column("active_calibrator_version", sa.String(length=96), nullable=True),
        sa.Column("account_ids_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("checks_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("plan_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("tracked_job_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("actual_successful_jobs", sa.Integer(), nullable=True),
        sa.Column("actual_failed_jobs", sa.Integer(), nullable=True),
        sa.Column("actual_cancelled_jobs", sa.Integer(), nullable=True),
        sa.Column("actual_completion_rate", sa.Float(), nullable=True),
        sa.Column("actual_met_execution_plan", sa.Boolean(), nullable=True),
        sa.Column("label_finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("label_notes", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_preflight_decisions_owner_id", "campaign_preflight_decisions", ["owner_id"])
    op.create_index("ix_campaign_preflight_decisions_campaign_id", "campaign_preflight_decisions", ["campaign_id"])
    op.create_index("ix_campaign_preflight_decisions_decision", "campaign_preflight_decisions", ["decision"])
    op.create_index("ix_campaign_preflight_decisions_deadline_at", "campaign_preflight_decisions", ["deadline_at"])
    op.create_index("ix_campaign_preflight_decisions_label_status", "campaign_preflight_decisions", ["label_status"])
    op.create_index("ix_campaign_preflight_decisions_owner_created", "campaign_preflight_decisions", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_campaign_preflight_decisions_owner_created", table_name="campaign_preflight_decisions")
    op.drop_index("ix_campaign_preflight_decisions_label_status", table_name="campaign_preflight_decisions")
    op.drop_index("ix_campaign_preflight_decisions_deadline_at", table_name="campaign_preflight_decisions")
    op.drop_index("ix_campaign_preflight_decisions_decision", table_name="campaign_preflight_decisions")
    op.drop_index("ix_campaign_preflight_decisions_campaign_id", table_name="campaign_preflight_decisions")
    op.drop_index("ix_campaign_preflight_decisions_owner_id", table_name="campaign_preflight_decisions")
    op.drop_table("campaign_preflight_decisions")
