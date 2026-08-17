"""track immutable allocation consumption by campaigns

Revision ID: 20260818_000015
Revises: 20260818_000014
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000015"
down_revision = "20260818_000014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capacity_allocation_assignments",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "capacity_allocation_assignments",
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_capacity_allocation_assignments_campaign_id",
        "capacity_allocation_assignments",
        "invite_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_capacity_allocation_assignments_campaign_id",
        "capacity_allocation_assignments",
        ["campaign_id"],
    )
    op.create_index(
        "ix_capacity_allocation_assignments_plan_segment_consumed",
        "capacity_allocation_assignments",
        ["plan_id", "segment_id", "consumed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capacity_allocation_assignments_plan_segment_consumed",
        table_name="capacity_allocation_assignments",
    )
    op.drop_index(
        "ix_capacity_allocation_assignments_campaign_id",
        table_name="capacity_allocation_assignments",
    )
    op.drop_constraint(
        "fk_capacity_allocation_assignments_campaign_id",
        "capacity_allocation_assignments",
        type_="foreignkey",
    )
    op.drop_column("capacity_allocation_assignments", "consumed_at")
    op.drop_column("capacity_allocation_assignments", "campaign_id")
