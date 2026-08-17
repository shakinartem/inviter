"""make accounts platform neutral

Revision ID: 20260817_000003
Revises: 20260817_000002
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_000003"
down_revision = "20260817_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="telegram"),
    )
    op.add_column(
        "accounts",
        sa.Column("external_account_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="session"),
    )
    op.add_column(
        "accounts",
        sa.Column("credential_payload_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("capabilities", sa.JSON(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("health_score", sa.Float(), nullable=False, server_default="100"),
    )

    # Existing rows are Telegram accounts. Keep their identity when it is known.
    op.execute(
        "UPDATE accounts SET external_account_id = telegram_user_id::text "
        "WHERE telegram_user_id IS NOT NULL AND external_account_id IS NULL"
    )

    # Other platforms do not use Telethon session files.
    op.alter_column(
        "accounts",
        "session_name",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.create_index("ix_accounts_platform", "accounts", ["platform"], unique=False)
    op.create_index(
        "ix_accounts_external_account_id",
        "accounts",
        ["external_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_accounts_owner_platform",
        "accounts",
        ["owner_id", "platform"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_accounts_owner_platform_external",
        "accounts",
        ["owner_id", "platform", "external_account_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_accounts_owner_platform_external", "accounts", type_="unique")
    op.drop_index("ix_accounts_owner_platform", table_name="accounts")
    op.drop_index("ix_accounts_external_account_id", table_name="accounts")
    op.drop_index("ix_accounts_platform", table_name="accounts")

    # Make downgrade possible even if non-Telegram rows were created.
    op.execute(
        "UPDATE accounts SET session_name = 'legacy_' || replace(id::text, '-', '') "
        "WHERE session_name IS NULL"
    )
    op.alter_column(
        "accounts",
        "session_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_column("accounts", "health_score")
    op.drop_column("accounts", "capabilities")
    op.drop_column("accounts", "credential_payload_encrypted")
    op.drop_column("accounts", "auth_type")
    op.drop_column("accounts", "external_account_id")
    op.drop_column("accounts", "platform")
