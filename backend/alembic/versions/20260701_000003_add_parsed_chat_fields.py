"""Add missing parsed_chats fields to match SQLAlchemy model

Revision ID: 20260701_000003
Revises: 20260701_000002
Create Date: 2026-07-01 10:11:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import text


revision = "20260701_000003"
down_revision = "20260701_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename telegram_chat_id to chat_id to match model
    op.alter_column("parsed_chats", "telegram_chat_id", new_column_name="chat_id", existing_type=sa.BigInteger(), nullable=False)
    # chat_id already exists, ensure it remains NOT NULL after rename
    
    # NOTE: username, title, access_hash already exist from initial migration
    # Only add columns that don't already exist
    op.add_column("parsed_chats", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("parsed_chats", sa.Column("chat_type", sa.String(32), nullable=True))
    op.add_column("parsed_chats", sa.Column("participants_count", sa.Integer(), nullable=True))
    op.add_column("parsed_chats", sa.Column("active_participants", sa.Integer(), nullable=True))
    op.add_column("parsed_chats", sa.Column("category", sa.String(120), nullable=True))
    op.add_column("parsed_chats", sa.Column("niche", sa.String(120), nullable=True))
    op.add_column("parsed_chats", sa.Column("tags", sa.ARRAY(sa.String(64)), nullable=True))
    op.add_column("parsed_chats", sa.Column("language", sa.String(10), nullable=True))
    op.add_column("parsed_chats", sa.Column("country", sa.String(10), nullable=True))
    op.add_column("parsed_chats", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=text("true")))
    op.add_column("parsed_chats", sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default=text("false")))
    op.add_column("parsed_chats", sa.Column("source", sa.String(32), nullable=False, server_default=text("'manual'")))
    op.add_column("parsed_chats", sa.Column("last_parsed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("parsed_chats", sa.Column("parse_count", sa.Integer(), nullable=False, server_default=text("1")))
    op.add_column("parsed_chats", sa.Column("avg_posts_per_day", sa.Float(), nullable=True))
    op.add_column("parsed_chats", sa.Column("avg_reach_per_post", sa.Integer(), nullable=True))
    op.add_column("parsed_chats", sa.Column("engagement_rate", sa.Float(), nullable=True))
    op.add_column("parsed_chats", sa.Column("extra_data", sa.JSON(), nullable=True))
    
    # Ensure chat_id remains NOT NULL after rename
    op.alter_column("parsed_chats", "chat_id", existing_type=sa.BigInteger(), nullable=False)
    
    # Add indices
    op.create_index("ix_parsed_chats_chat_id", "parsed_chats", ["chat_id"])
    op.create_index("ix_parsed_chats_username", "parsed_chats", ["username"])
    op.create_index("ix_parsed_chats_category", "parsed_chats", ["category"])
    op.create_index("ix_parsed_chats_niche", "parsed_chats", ["niche"])
    op.create_index("ix_parsed_chats_language", "parsed_chats", ["language"])
    op.create_index("ix_parsed_chats_source", "parsed_chats", ["source"])
    op.create_index("ix_parsed_chats_is_active", "parsed_chats", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_parsed_chats_is_active", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_source", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_language", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_niche", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_category", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_username", table_name="parsed_chats")
    op.drop_index("ix_parsed_chats_chat_id", table_name="parsed_chats")
    
    op.drop_column("parsed_chats", "extra_data")
    op.drop_column("parsed_chats", "engagement_rate")
    op.drop_column("parsed_chats", "avg_reach_per_post")
    op.drop_column("parsed_chats", "avg_posts_per_day")
    op.drop_column("parsed_chats", "parse_count")
    op.drop_column("parsed_chats", "last_parsed_at")
    op.drop_column("parsed_chats", "source")
    op.drop_column("parsed_chats", "is_restricted")
    op.drop_column("parsed_chats", "is_public")
    op.drop_column("parsed_chats", "country")
    op.drop_column("parsed_chats", "language")
    op.drop_column("parsed_chats", "tags")
    op.drop_column("parsed_chats", "niche")
    op.drop_column("parsed_chats", "category")
    op.drop_column("parsed_chats", "active_participants")
    op.drop_column("parsed_chats", "participants_count")
    op.drop_column("parsed_chats", "chat_type")
    op.drop_column("parsed_chats", "description")
    
    # Rename back
    op.alter_column("parsed_chats", "chat_id", new_column_name="telegram_chat_id", existing_type=sa.BigInteger(), nullable=False)