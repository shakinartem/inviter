"""Add username, password, local_adapter fields to proxy_candidates

Revision ID: 20260613_000002
Revises: 20260613_000001
Create Date: 2026-06-13 17:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260613_000002"
down_revision = "20260613_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add username and password columns
    op.add_column("proxy_candidates", sa.Column("username", sa.String(255), nullable=True))
    op.add_column("proxy_candidates", sa.Column("password", sa.String(255), nullable=True))
    
    # Update check constraints
    # Due to naming_convention in app/db/base.py (ck_%(table_name)s_%(constraint_name)s),
    # op.create_check_constraint with name "ck_proxy_candidates_*" double-prefixes.
    # So we DROP the original constraint name from migration 000001 first,
    # then recreate without the naming_convention prefix by using raw SQL.
    
    # Drop the old constraints (created by migration 000001 via op.create_table)
    # These were created WITHOUT the naming_convention, so name is as given.
    op.execute("ALTER TABLE proxy_candidates DROP CONSTRAINT IF EXISTS ck_proxy_candidates_proxy_type")
    op.execute("ALTER TABLE proxy_candidates DROP CONSTRAINT IF EXISTS ck_proxy_candidates_source_type")
    
    # Recreate with new values
    op.execute(
        "ALTER TABLE proxy_candidates "
        "ADD CONSTRAINT ck_proxy_candidates_proxy_type "
        "CHECK (proxy_type IN ('socks5', 'http', 'mtproto', 'local_adapter', 'unknown'))"
    )
    op.execute(
        "ALTER TABLE proxy_candidates "
        "ADD CONSTRAINT ck_proxy_candidates_source_type "
        "CHECK (source_type IN ('manual_text', 'mtproto_text', 'telegram_channel', 'url_list', 'local_adapter'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE proxy_candidates DROP CONSTRAINT IF EXISTS ck_proxy_candidates_proxy_type")
    op.execute("ALTER TABLE proxy_candidates DROP CONSTRAINT IF EXISTS ck_proxy_candidates_source_type")
    
    op.execute(
        "ALTER TABLE proxy_candidates "
        "ADD CONSTRAINT ck_proxy_candidates_proxy_type "
        "CHECK (proxy_type IN ('mtproto', 'http', 'socks5'))"
    )
    op.execute(
        "ALTER TABLE proxy_candidates "
        "ADD CONSTRAINT ck_proxy_candidates_source_type "
        "CHECK (source_type IN ('manual_text', 'telegram_channel'))"
    )
    
    op.drop_column("proxy_candidates", "password")
    op.drop_column("proxy_candidates", "username")