"""add frozen capacity allocation plans

Revision ID: 20260818_000014
Revises: 20260818_000013
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000014"
down_revision = "20260818_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capacity_allocation_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("allocation_mode", sa.String(length=32), nullable=False, server_default="decision_grade"),
        sa.Column("require_positive_conservative", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="frozen"),
        sa.Column("evidence_version", sa.String(length=64), nullable=False, server_default="causal-allocation-v1"),
        sa.Column("offers_considered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_offers_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unallocated_capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_incremental_outcomes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("conservative_incremental_outcomes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("upside_incremental_outcomes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("replicated_context_coverage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("global_prior_status", sa.String(length=32), nullable=False),
        sa.Column("global_prior_lift", sa.Float(), nullable=False, server_default="0"),
        sa.Column("global_prior_i_squared", sa.Float(), nullable=False, server_default="0"),
        sa.Column("candidate_pool_capped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warnings", postgresql.JSON(), nullable=True),
        sa.Column("source_snapshot", postgresql.JSON(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capacity_allocation_plans_owner_id", "capacity_allocation_plans", ["owner_id"])
    op.create_index("ix_capacity_allocation_plans_platform", "capacity_allocation_plans", ["platform"])
    op.create_index("ix_capacity_allocation_plans_status", "capacity_allocation_plans", ["status"])
    op.create_index("ix_capacity_allocation_plans_frozen_at", "capacity_allocation_plans", ["frozen_at"])
    op.create_index("ix_capacity_allocation_plans_owner_frozen", "capacity_allocation_plans", ["owner_id", "frozen_at"])

    op.create_table(
        "capacity_allocation_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocation_rank", sa.Integer(), nullable=False),
        sa.Column("segment_rank", sa.Integer(), nullable=False),
        sa.Column("segment_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("segment_refresh_sequence", sa.Integer(), nullable=False),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("strongest_signal_type", sa.String(length=64), nullable=True),
        sa.Column("match_reasons", postgresql.JSON(), nullable=True),
        sa.Column("evidence_source", sa.String(length=32), nullable=False),
        sa.Column("context_key", sa.String(length=160), nullable=False),
        sa.Column("expected_incremental_probability", sa.Float(), nullable=False),
        sa.Column("conservative_incremental_probability", sa.Float(), nullable=False),
        sa.Column("upside_incremental_probability", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["capacity_allocation_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["audience_segments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "audience_member_id", name="uq_capacity_allocation_plan_member"),
    )
    op.create_index("ix_capacity_allocation_assignments_plan_id", "capacity_allocation_assignments", ["plan_id"])
    op.create_index("ix_capacity_allocation_assignments_owner_id", "capacity_allocation_assignments", ["owner_id"])
    op.create_index("ix_capacity_allocation_assignments_segment_id", "capacity_allocation_assignments", ["segment_id"])
    op.create_index("ix_capacity_allocation_assignments_audience_member_id", "capacity_allocation_assignments", ["audience_member_id"])
    op.create_index("ix_capacity_allocation_assignments_plan_segment", "capacity_allocation_assignments", ["plan_id", "segment_id"])
    op.create_index("ix_capacity_allocation_assignments_plan_rank", "capacity_allocation_assignments", ["plan_id", "allocation_rank"])


def downgrade() -> None:
    op.drop_table("capacity_allocation_assignments")
    op.drop_table("capacity_allocation_plans")
