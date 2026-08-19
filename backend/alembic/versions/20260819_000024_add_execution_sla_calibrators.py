"""add execution sla calibrators

Revision ID: 20260819_000024
Revises: 20260819_000023
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_000024"
down_revision = "20260819_000023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_sla_calibrators",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_model_version", sa.String(length=64), nullable=False),
        sa.Column("calibrator_version", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("train_count", sa.Integer(), nullable=False),
        sa.Column("test_count", sa.Integer(), nullable=False),
        sa.Column("training_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_brier_test", sa.Float(), nullable=False),
        sa.Column("calibrated_brier_test", sa.Float(), nullable=False),
        sa.Column("raw_ece_test", sa.Float(), nullable=False),
        sa.Column("calibrated_ece_test", sa.Float(), nullable=False),
        sa.Column("raw_bias_test", sa.Float(), nullable=False),
        sa.Column("calibrated_bias_test", sa.Float(), nullable=False),
        sa.Column("mapping", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("training_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_sla_calibrators_owner_id", "execution_sla_calibrators", ["owner_id"])
    op.create_index("ix_execution_sla_calibrators_base_model_version", "execution_sla_calibrators", ["base_model_version"])
    op.create_index("ix_execution_sla_calibrators_calibrator_version", "execution_sla_calibrators", ["calibrator_version"])
    op.create_index("ix_execution_sla_calibrators_status", "execution_sla_calibrators", ["status"])
    op.create_index("ix_execution_sla_calibrators_trained_at", "execution_sla_calibrators", ["trained_at"])
    op.create_index("ix_execution_sla_calibrators_owner_status", "execution_sla_calibrators", ["owner_id", "status"])
    op.create_index("ix_execution_sla_calibrators_owner_model", "execution_sla_calibrators", ["owner_id", "base_model_version"])


def downgrade() -> None:
    op.drop_index("ix_execution_sla_calibrators_owner_model", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_owner_status", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_trained_at", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_status", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_calibrator_version", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_base_model_version", table_name="execution_sla_calibrators")
    op.drop_index("ix_execution_sla_calibrators_owner_id", table_name="execution_sla_calibrators")
    op.drop_table("execution_sla_calibrators")
