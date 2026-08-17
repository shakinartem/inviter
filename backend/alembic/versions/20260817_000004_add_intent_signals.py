"""add versioned intent signals

Revision ID: 20260817_000004
Revises: 20260817_000003
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000004"
down_revision = "20260817_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intent_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parsed_chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("message_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsed_chat_id"], ["parsed_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "platform",
            "message_fingerprint",
            "model_version",
            name="uq_intent_signal_message_model",
        ),
    )
    op.create_index("ix_intent_signals_owner_id", "intent_signals", ["owner_id"], unique=False)
    op.create_index("ix_intent_signals_audience_member_id", "intent_signals", ["audience_member_id"], unique=False)
    op.create_index("ix_intent_signals_parsed_chat_id", "intent_signals", ["parsed_chat_id"], unique=False)
    op.create_index("ix_intent_signals_platform", "intent_signals", ["platform"], unique=False)
    op.create_index("ix_intent_signals_message_fingerprint", "intent_signals", ["message_fingerprint"], unique=False)
    op.create_index("ix_intent_signals_observed_at", "intent_signals", ["observed_at"], unique=False)
    op.create_index("ix_intent_signals_signal_type", "intent_signals", ["signal_type"], unique=False)
    op.create_index("ix_intent_signals_topic", "intent_signals", ["topic"], unique=False)
    op.create_index("ix_intent_signals_score", "intent_signals", ["score"], unique=False)
    op.create_index("ix_intent_signals_model_version", "intent_signals", ["model_version"], unique=False)
    op.create_index(
        "ix_intent_signals_member_observed",
        "intent_signals",
        ["audience_member_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_intent_signals_member_score",
        "intent_signals",
        ["audience_member_id", "score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_intent_signals_member_score", table_name="intent_signals")
    op.drop_index("ix_intent_signals_member_observed", table_name="intent_signals")
    op.drop_index("ix_intent_signals_model_version", table_name="intent_signals")
    op.drop_index("ix_intent_signals_score", table_name="intent_signals")
    op.drop_index("ix_intent_signals_topic", table_name="intent_signals")
    op.drop_index("ix_intent_signals_signal_type", table_name="intent_signals")
    op.drop_index("ix_intent_signals_observed_at", table_name="intent_signals")
    op.drop_index("ix_intent_signals_message_fingerprint", table_name="intent_signals")
    op.drop_index("ix_intent_signals_platform", table_name="intent_signals")
    op.drop_index("ix_intent_signals_parsed_chat_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_audience_member_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_owner_id", table_name="intent_signals")
    op.drop_table("intent_signals")
