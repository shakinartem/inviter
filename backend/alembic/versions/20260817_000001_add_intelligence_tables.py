"""add audience intelligence tables

Revision ID: 20260817_000001
Revises: 20260609_000002
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000001"
down_revision = "20260609_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parsed_chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("participants_count", sa.Integer(), nullable=True),
        sa.Column("active_1d", sa.Integer(), nullable=True),
        sa.Column("active_7d", sa.Integer(), nullable=True),
        sa.Column("messages_1d", sa.Integer(), nullable=True),
        sa.Column("messages_7d", sa.Integer(), nullable=True),
        sa.Column("unique_authors_1d", sa.Integer(), nullable=True),
        sa.Column("unique_authors_7d", sa.Integer(), nullable=True),
        sa.Column("bot_ratio", sa.Float(), nullable=True),
        sa.Column("spam_ratio", sa.Float(), nullable=True),
        sa.Column("growth_rate_30d", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsed_chat_id"], ["parsed_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_community_snapshots_owner_id", "community_snapshots", ["owner_id"])
    op.create_index("ix_community_snapshots_parsed_chat_id", "community_snapshots", ["parsed_chat_id"])
    op.create_index("ix_community_snapshots_captured_at", "community_snapshots", ["captured_at"])
    op.create_index("ix_community_snapshots_quality_score", "community_snapshots", ["quality_score"])
    op.create_index("ix_community_snapshots_chat_captured", "community_snapshots", ["parsed_chat_id", "captured_at"])

    op.create_table(
        "audience_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_scam", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_fake", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "platform", "external_user_id", name="uq_audience_member_identity"),
    )
    for column in ("owner_id", "platform", "external_user_id", "username", "is_blacklisted", "last_activity_at", "activity_score", "relevance_score", "quality_score", "intent_score", "readiness_score"):
        op.create_index(f"ix_audience_members_{column}", "audience_members", [column])
    op.create_index("ix_audience_members_owner_readiness", "audience_members", ["owner_id", "readiness_score"])

    op.create_table(
        "community_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parsed_chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages_7d", sa.Integer(), nullable=True),
        sa.Column("messages_30d", sa.Integer(), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsed_chat_id"], ["parsed_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audience_member_id", "parsed_chat_id", name="uq_member_community"),
    )
    op.create_index("ix_community_memberships_audience_member_id", "community_memberships", ["audience_member_id"])
    op.create_index("ix_community_memberships_parsed_chat_id", "community_memberships", ["parsed_chat_id"])
    op.create_index("ix_community_memberships_last_seen_at", "community_memberships", ["last_seen_at"])


def downgrade() -> None:
    op.drop_table("community_memberships")
    op.drop_table("audience_members")
    op.drop_table("community_snapshots")
