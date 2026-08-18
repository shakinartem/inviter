"""add execution sla forecast snapshots

Revision ID: 20260819_000021
Revises: 20260819_000020
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000021"
down_revision = "20260819_000020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_sla_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("remaining_actions", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_sla", sa.Float(), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("evidence_quality", sa.String(length=32), nullable=False),
        sa.Column("current_reserve_percentage", sa.Float(), nullable=False),
        sa.Column("recommended_reserve_percentage", sa.Float(), nullable=True),
        sa.Column("recommended_modelled_continuity_probability", sa.Float(), nullable=True),
        sa.Column("recommended_conservative_continuity_probability", sa.Float(), nullable=True),
        sa.Column("normal_daily_capacity", sa.Integer(), nullable=False),
        sa.Column("emergency_daily_capacity", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("scenarios_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("actual_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_met_sla", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["invite_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_sla_forecasts_owner_id", "execution_sla_forecasts", ["owner_id"])
    op.create_index("ix_execution_sla_forecasts_campaign_id", "execution_sla_forecasts", ["campaign_id"])
    op.create_index("ix_execution_sla_forecasts_model_version", "execution_sla_forecasts", ["model_version"])
    op.create_index("ix_execution_sla_forecasts_deadline_at", "execution_sla_forecasts", ["deadline_at"])
    op.create_index("ix_execution_sla_forecasts_evidence_quality", "execution_sla_forecasts", ["evidence_quality"])
    op.create_index(
        "ix_execution_sla_forecasts_owner_created",
        "execution_sla_forecasts",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_execution_sla_forecasts_campaign_created",
        "execution_sla_forecasts",
        ["campaign_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_sla_forecasts_campaign_created", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_owner_created", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_evidence_quality", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_deadline_at", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_model_version", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_campaign_id", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_owner_id", table_name="execution_sla_forecasts")
    op.drop_table("execution_sla_forecasts")
