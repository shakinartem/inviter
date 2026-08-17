"""add signed outcome webhook sources

Revision ID: 20260818_000011
Revises: 20260817_000010
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_000011"
down_revision = "20260817_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outcome_webhook_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("allowed_stages", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[\"business\"]'::json")),
        sa.Column("allowed_event_types", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("delivery_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("secret_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_outcome_webhook_source_owner_slug"),
    )
    op.create_index("ix_outcome_webhook_sources_owner_id", "outcome_webhook_sources", ["owner_id"])
    op.create_index("ix_outcome_webhook_sources_is_active", "outcome_webhook_sources", ["is_active"])
    op.create_index(
        "ix_outcome_webhook_sources_owner_active",
        "outcome_webhook_sources",
        ["owner_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("outcome_webhook_sources")
