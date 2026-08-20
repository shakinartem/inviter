"""reconcile parser schema with current ORM

Revision ID: 20260817_000004a
Revises: 20260817_000004
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_000004a"
down_revision = "20260817_000004"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def _index_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _column_names(table):
        op.add_column(table, column)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    # The original 2026-06 schema used legacy names while the parser ORM evolved
    # without a matching Alembic revision. Reconcile that drift before newer
    # intelligence/destination migrations depend on these columns.
    columns = _column_names("parsed_chats")
    if "telegram_chat_id" in columns and "chat_id" not in columns:
        op.alter_column("parsed_chats", "telegram_chat_id", new_column_name="chat_id")
    columns = _column_names("parsed_chats")
    if "members_count" in columns and "participants_count" not in columns:
        op.alter_column("parsed_chats", "members_count", new_column_name="participants_count")

    # Current parser model allows missing titles (some connector/catalog sources
    # can resolve an identity before a display name).
    if "title" in _column_names("parsed_chats"):
        op.alter_column(
            "parsed_chats",
            "title",
            existing_type=sa.String(length=255),
            type_=sa.String(length=512),
            nullable=True,
        )

    additions = [
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chat_type", sa.String(length=32), nullable=True),
        sa.Column("active_participants", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("niche", sa.String(length=120), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=64)), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("country", sa.String(length=10), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("last_parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("avg_posts_per_day", sa.Float(), nullable=True),
        sa.Column("avg_reach_per_post", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
    ]
    for column in additions:
        _add_column_if_missing("parsed_chats", column)

    # Historical rows predate chat_type. Keep the fallback intentionally generic;
    # the next authorized Telegram sync will replace it with group/supergroup/channel.
    op.execute(
        """
        UPDATE parsed_chats
        SET chat_type = COALESCE(chat_type, 'group'),
            is_public = COALESCE(is_public, username IS NOT NULL),
            source = COALESCE(source, 'manual'),
            parse_count = COALESCE(parse_count, 1)
        """
    )

    _create_index_if_missing("ix_parsed_chats_owner_id", "parsed_chats", ["owner_id"])
    _create_index_if_missing("ix_parsed_chats_chat_id", "parsed_chats", ["chat_id"])
    _create_index_if_missing("ix_parsed_chats_username", "parsed_chats", ["username"])
    _create_index_if_missing("ix_parsed_chats_category", "parsed_chats", ["category"])
    _create_index_if_missing("ix_parsed_chats_niche", "parsed_chats", ["niche"])
    _create_index_if_missing("ix_parsed_chats_language", "parsed_chats", ["language"])
    _create_index_if_missing("ix_parsed_chats_is_active", "parsed_chats", ["is_active"])
    _create_index_if_missing("ix_parsed_chats_source", "parsed_chats", ["source"])

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("parsed_users"):
        op.create_table(
            "parsed_users",
            sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("first_name", sa.String(length=120), nullable=True),
            sa.Column("last_name", sa.String(length=120), nullable=True),
            sa.Column("phone", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_scam", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_fake", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            sa.Column("was_online_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("msg_count", sa.Integer(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["chat_id"], ["parsed_chats.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_parsed_users_owner_id", "parsed_users", ["owner_id"], unique=False)
        op.create_index("ix_parsed_users_chat_id", "parsed_users", ["chat_id"], unique=False)
        op.create_index("ix_parsed_users_user_id", "parsed_users", ["user_id"], unique=False)
        op.create_index("ix_parsed_users_username", "parsed_users", ["username"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("parsed_users"):
        op.drop_table("parsed_users")

    for index_name in (
        "ix_parsed_chats_source",
        "ix_parsed_chats_is_active",
        "ix_parsed_chats_language",
        "ix_parsed_chats_niche",
        "ix_parsed_chats_category",
        "ix_parsed_chats_username",
        "ix_parsed_chats_chat_id",
        "ix_parsed_chats_owner_id",
    ):
        if index_name in _index_names("parsed_chats"):
            op.drop_index(index_name, table_name="parsed_chats")

    for column_name in (
        "extra_data",
        "engagement_rate",
        "avg_reach_per_post",
        "avg_posts_per_day",
        "parse_count",
        "last_parsed_at",
        "source",
        "is_restricted",
        "is_public",
        "country",
        "language",
        "tags",
        "niche",
        "category",
        "active_participants",
        "chat_type",
        "description",
    ):
        if column_name in _column_names("parsed_chats"):
            op.drop_column("parsed_chats", column_name)

    columns = _column_names("parsed_chats")
    if "participants_count" in columns and "members_count" not in columns:
        op.alter_column("parsed_chats", "participants_count", new_column_name="members_count")
    columns = _column_names("parsed_chats")
    if "chat_id" in columns and "telegram_chat_id" not in columns:
        op.alter_column("parsed_chats", "chat_id", new_column_name="telegram_chat_id")
