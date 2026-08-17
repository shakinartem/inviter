"""add value-aware capacity allocation objective

Revision ID: 20260818_000017
Revises: 20260818_000016
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260818_000017"
down_revision = "20260818_000016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("capacity_allocation_plans", sa.Column("objective", sa.String(length=40), nullable=False, server_default="incremental_outcomes"))
    op.add_column("capacity_allocation_plans", sa.Column("value_unit", sa.String(length=16), nullable=True))
    op.add_column("capacity_allocation_plans", sa.Column("value_aggregation", sa.String(length=16), nullable=True))
    op.add_column("capacity_allocation_plans", sa.Column("expected_incremental_business_value", sa.Float(), nullable=True))
    op.add_column("capacity_allocation_plans", sa.Column("conservative_incremental_business_value", sa.Float(), nullable=True))
    op.add_column("capacity_allocation_plans", sa.Column("upside_incremental_business_value", sa.Float(), nullable=True))
    op.create_index("ix_capacity_allocation_plans_objective", "capacity_allocation_plans", ["objective"])
    op.create_index("ix_capacity_allocation_plans_value_unit", "capacity_allocation_plans", ["value_unit"])

    op.alter_column("capacity_allocation_assignments", "expected_incremental_probability", existing_type=sa.Float(), nullable=True)
    op.alter_column("capacity_allocation_assignments", "conservative_incremental_probability", existing_type=sa.Float(), nullable=True)
    op.alter_column("capacity_allocation_assignments", "upside_incremental_probability", existing_type=sa.Float(), nullable=True)
    op.add_column("capacity_allocation_assignments", sa.Column("expected_incremental_business_value", sa.Float(), nullable=True))
    op.add_column("capacity_allocation_assignments", sa.Column("conservative_incremental_business_value", sa.Float(), nullable=True))
    op.add_column("capacity_allocation_assignments", sa.Column("upside_incremental_business_value", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("capacity_allocation_assignments", "upside_incremental_business_value")
    op.drop_column("capacity_allocation_assignments", "conservative_incremental_business_value")
    op.drop_column("capacity_allocation_assignments", "expected_incremental_business_value")
    op.alter_column("capacity_allocation_assignments", "upside_incremental_probability", existing_type=sa.Float(), nullable=False)
    op.alter_column("capacity_allocation_assignments", "conservative_incremental_probability", existing_type=sa.Float(), nullable=False)
    op.alter_column("capacity_allocation_assignments", "expected_incremental_probability", existing_type=sa.Float(), nullable=False)

    op.drop_index("ix_capacity_allocation_plans_value_unit", table_name="capacity_allocation_plans")
    op.drop_index("ix_capacity_allocation_plans_objective", table_name="capacity_allocation_plans")
    op.drop_column("capacity_allocation_plans", "upside_incremental_business_value")
    op.drop_column("capacity_allocation_plans", "conservative_incremental_business_value")
    op.drop_column("capacity_allocation_plans", "expected_incremental_business_value")
    op.drop_column("capacity_allocation_plans", "value_aggregation")
    op.drop_column("capacity_allocation_plans", "value_unit")
    op.drop_column("capacity_allocation_plans", "objective")
