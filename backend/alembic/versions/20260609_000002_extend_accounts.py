"""extend accounts table: profile fields, metrics, cooldown/banned, extra_data

Revision ID: 20260609_000002
Revises: 20260609_000001
Create Date: 2026-06-09 19:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260609_000002"
down_revision = "20260609_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================== Profile fields (from check_account) ====================
    op.add_column(
        "accounts",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_accounts_telegram_user_id", "accounts", ["telegram_user_id"], unique=True
    )
    op.add_column(
        "accounts",
        sa.Column("first_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("last_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("username", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "accounts",
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # ==================== Status messaging ====================
    op.add_column(
        "accounts",
        sa.Column("status_message", sa.String(length=500), nullable=True),
    )

    # ==================== Last-seen / last-used / last-checked ====================
    op.add_column(
        "accounts",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    # last_seen_at уже есть в предыдущей миграции

    # ==================== Cooldown / banned windows ====================
    op.add_column(
        "accounts",
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_accounts_cooldown_until", "accounts", ["cooldown_until"]
    )
    op.create_index(
        "ix_accounts_banned_until", "accounts", ["banned_until"]
    )

    # ==================== Metrics ====================
    op.add_column(
        "accounts",
        sa.Column(
            "daily_invite_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "daily_invite_reset_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "total_invites",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "total_invite_errors",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "total_floodwaits",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "success_rate",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
    )

    # ==================== JSONB metadata ====================
    op.add_column(
        "accounts",
        sa.Column("extra_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

    # ==================== Indexes for fast filtering ====================
    op.create_index(
        "ix_accounts_is_premium", "accounts", ["is_premium"]
    )
    op.create_index(
        "ix_accounts_status_is_active",
        "accounts",
        ["status", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_status_is_active", table_name="accounts")
    op.drop_index("ix_accounts_is_premium", table_name="accounts")
    op.drop_column("accounts", "extra_data")
    op.drop_column("accounts", "success_rate")
    op.drop_column("accounts", "total_floodwaits")
    op.drop_column("accounts", "total_invite_errors")
    op.drop_column("accounts", "total_invites")
    op.drop_column("accounts", "daily_invite_reset_at")
    op.drop_column("accounts", "daily_invite_count")
    op.drop_index("ix_accounts_banned_until", table_name="accounts")
    op.drop_index("ix_accounts_cooldown_until", table_name="accounts")
    op.drop_column("accounts", "banned_until")
    op.drop_column("accounts", "cooldown_until")
    op.drop_column("accounts", "last_checked_at")
    op.drop_column("accounts", "last_used_at")
    op.drop_column("accounts", "status_message")
    op.drop_column("accounts", "is_bot")
    op.drop_column("accounts", "is_premium")
    op.drop_column("accounts", "username")
    op.drop_column("accounts", "last_name")
    op.drop_column("accounts", "first_name")
    op.drop_index("ix_accounts_telegram_user_id", table_name="accounts")
    op.drop_column("accounts", "telegram_user_id")
