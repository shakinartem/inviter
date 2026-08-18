"""add execution sla calibration labels

Revision ID: 20260819_000022
Revises: 20260819_000021
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000022"
down_revision = "20260819_000021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("label_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("queue_eligible_at_forecast", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("actual_successful_actions", sa.Integer(), nullable=True),
    )
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("actual_hard_failure_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("label_finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_sla_forecasts",
        sa.Column("label_notes", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_execution_sla_forecasts_label_status", "execution_sla_forecasts", ["label_status"])
    op.create_index("ix_execution_sla_forecasts_label_finalized_at", "execution_sla_forecasts", ["label_finalized_at"])


def downgrade() -> None:
    op.drop_index("ix_execution_sla_forecasts_label_finalized_at", table_name="execution_sla_forecasts")
    op.drop_index("ix_execution_sla_forecasts_label_status", table_name="execution_sla_forecasts")
    op.drop_column("execution_sla_forecasts", "label_notes")
    op.drop_column("execution_sla_forecasts", "label_finalized_at")
    op.drop_column("execution_sla_forecasts", "actual_hard_failure_days")
    op.drop_column("execution_sla_forecasts", "actual_successful_actions")
    op.drop_column("execution_sla_forecasts", "queue_eligible_at_forecast")
    op.drop_column("execution_sla_forecasts", "label_status")
