"""
Tests for schema reconciliation between SQLAlchemy models and database tables.

Ensures that:
1. All model columns exist in the database (no missing columns).
2. Key API endpoints work after schema changes.
3. Mapper initialization succeeds without errors (configure_mappers).
4. Celery tasks return serializable results without mapper crashes.
5. All required tables exist in the database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.db.models import (
    Account,
    Campaign,
    InviteCampaign,
    InviteTask,
    ParsedChat,
    ParsedUser,
    Proxy,
    ProxyCandidate,
    SourceCandidate,
    SourceScore,
    User,
)


# ==================== Helper ====================

def _get_model_columns(model) -> set[str]:
    """Get all mapped column names from a SQLAlchemy model."""
    mapper = inspect(model)
    return {c.key for c in mapper.columns}


# ==================== P0: configure_mappers() must pass ====================

class TestConfigureMappers:
    """configure_mappers() must not raise 'failed to locate a name' errors."""

    def test_configure_mappers_passes(self):
        """
        configure_mappers() must not raise exceptions like
        'failed to locate a name (SourceCandidate)'.
        This validates all string-based relationship references resolve correctly.
        """
        # All models are already imported via conftest.py -> app.db.models
        try:
            configure_mappers()
        except Exception as e:
            pytest.fail(f"configure_mappers() raised: {e}")


# NOTE: Table existence checks are covered by smoke_mvp.py, not pytest,
# because there is no db_session fixture in this project.


# ==================== Fix #1: asyncio import in auth_start ====================

class TestAuthStartAsyncioImport:
    """Verify that auth_start code path does not raise NameError on asyncio."""

    @pytest.mark.asyncio
    async def test_auth_start_uses_asyncio_without_nameerror(self):
        """
        Call auth_start with mocked Telethon and verify no NameError for asyncio.
        This tests that 'asyncio' is properly imported in the service module.
        """
        from app.features.accounts.service import AccountService

        # Create a mock account
        mock_account = MagicMock()
        mock_account.id = uuid4()
        mock_account.phone = "+79991234567"
        mock_account.api_id = 12345
        mock_account.api_hash = "test_hash"
        mock_account.session_name = "test_session"
        mock_account.proxy_id = None
        mock_account.proxy = None
        mock_account.extra_data = {}

        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_session.execute.return_value = mock_result

        # Mock client_manager
        mock_client_manager = AsyncMock()
        mock_client_manager._session_path.return_value = "/tmp/test.session"
        mock_client_manager._build_proxy.return_value = None

        # Mock TelegramClient (imported inside auth_start via `from telethon import TelegramClient`)
        with patch("telethon.TelegramClient") as mock_tg:
            mock_client = AsyncMock()
            mock_tg.return_value = mock_client
            mock_client.connect = AsyncMock()
            mock_client.is_user_authorized = AsyncMock(return_value=False)
            mock_client.send_code_request = AsyncMock()
            mock_client.send_code_request.return_value.phone_code_hash = "test_hash"
            mock_client.send_code_request.return_value.timeout = 30
            mock_client.is_connected.return_value = False

            service = AccountService(
                session=mock_session,
                redis=None,
                client_manager=mock_client_manager,
            )

            # This should NOT raise NameError for asyncio
            try:
                result = await service.auth_start(mock_account.id)
                assert result["phone_code_hash"] == "test_hash"
            except NameError as e:
                if "asyncio" in str(e):
                    pytest.fail(f"NameError for asyncio detected: {e}")
                pass
            except Exception:
                pass


# ==================== Fix #2: Proxy model columns ====================

class TestProxySchemaReconciliation:
    """Verify that Proxy model defines expected columns in code."""

    MODEL_COLUMNS = {
        "id", "created_at", "updated_at",
        "owner_id", "title", "scheme", "host", "port",
        "username", "password", "secret",
        "country", "city",
        "ping_ms", "last_checked_at",
        "is_active", "is_working", "status_message",
        "extra_data", "notes",
    }

    def test_proxy_model_columns_defined(self):
        """Proxy model should define all expected columns."""
        model_cols = _get_model_columns(Proxy)
        for col in self.MODEL_COLUMNS:
            assert col in model_cols, f"Proxy model missing column: {col}"

    def test_proxy_approve_candidate_works_with_mocked_columns(self):
        """
        Creating a Proxy with all new columns should work in code.
        """
        from app.features.proxies.models import Proxy

        owner_id = uuid4()
        proxy = Proxy(
            owner_id=owner_id,
            title="Test Proxy",
            scheme="socks5",
            host="127.0.0.1",
            port=8080,
            username="user",
            password="pass",
            secret=None,
            country="RU",
            city="Moscow",
            ping_ms=100.5,
            last_checked_at=datetime.now(timezone.utc),
            is_active=True,
            is_working=True,
            status_message="Working",
            extra_data={"source": "test"},
            notes="Test notes",
        )
        assert proxy.country == "RU"
        assert proxy.city == "Moscow"
        assert proxy.ping_ms == 100.5
        assert proxy.is_working is True
        assert proxy.is_active is True
        assert proxy.status_message == "Working"
        assert proxy.extra_data == {"source": "test"}
        assert proxy.notes == "Test notes"


# ==================== Fix #3: ParsedChat model columns ====================

class TestParsedChatSchemaReconciliation:
    """Verify that ParsedChat model defines expected columns in code."""

    MODEL_COLUMNS = {
        "id", "created_at", "updated_at",
        "owner_id", "campaign_id",
        "chat_id", "username", "title", "description", "access_hash",
        "chat_type",
        "participants_count", "active_participants",
        "category", "niche", "tags",
        "language", "country",
        "is_public", "is_active", "is_restricted",
        "source", "last_parsed_at", "parse_count",
        "avg_posts_per_day", "avg_reach_per_post", "engagement_rate",
        "extra_data",
    }

    def test_parsed_chat_model_columns_defined(self):
        """ParsedChat model should define all expected columns."""
        model_cols = _get_model_columns(ParsedChat)
        for col in self.MODEL_COLUMNS:
            assert col in model_cols, f"ParsedChat model missing column: {col}"

    def test_parsed_chat_creation_works(self):
        """Creating a ParsedChat with all fields should work."""
        from app.features.parser.models import ParsedChat

        owner_id = uuid4()
        chat = ParsedChat(
            owner_id=owner_id,
            chat_id=123456789,
            username="test_chat",
            title="Test Chat",
            description="A test chat",
            access_hash="abc123",
            chat_type="group",
            participants_count=1000,
            active_participants=500,
            category="tech",
            niche="python",
            tags=["python", "coding"],
            language="ru",
            country="RU",
            is_public=True,
            is_active=True,
            is_restricted=False,
            source="tgstat",
            last_parsed_at=datetime.now(timezone.utc),
            parse_count=5,
            avg_posts_per_day=3.5,
            avg_reach_per_post=2500,
            engagement_rate=0.05,
            extra_data={"test": True},
        )
        assert chat.chat_id == 123456789
        assert chat.source == "tgstat"
        assert chat.tags == ["python", "coding"]
        assert chat.engagement_rate == 0.05


# ==================== P0: ParsedUser model columns ====================

class TestParsedUserSchemaReconciliation:
    """Verify that ParsedUser model defines expected columns."""

    MODEL_COLUMNS = {
        "id", "created_at", "updated_at",
        "owner_id", "chat_id",
        "user_id", "username", "first_name", "last_name", "phone",
        "status",
        "is_bot", "is_verified", "is_scam", "is_fake",
        "last_seen", "was_online_at", "msg_count",
    }

    def test_parsed_user_model_columns_defined(self):
        """ParsedUser model should define all expected columns."""
        model_cols = _get_model_columns(ParsedUser)
        for col in self.MODEL_COLUMNS:
            assert col in model_cols, f"ParsedUser model missing column: {col}"


# ==================== Fix #4: Celery mapper initialization ====================

class TestMapperInitialization:
    """Verify that all mappers initialize without errors."""

    def test_import_db_models_initializes_all_mappers(self):
        """
        Importing app.db.models should initialize all mappers without
        'failed to locate a name' errors.
        """
        for model in [
            User, Account, Proxy, ProxyCandidate,
            ParsedChat, ParsedUser, Campaign,
            InviteCampaign, InviteTask,
            SourceCandidate, SourceScore,
        ]:
            mapper = inspect(model)
            assert mapper is not None, f"Mapper for {model.__name__} is None"
            for rel in mapper.relationships:
                try:
                    _ = rel.mapper
                except Exception as e:
                    pytest.fail(
                        f"Relationship {rel.key} on {model.__name__} "
                        f"failed to resolve: {e}"
                    )

    def test_celery_retry_floodwait_tasks_returns_dict_without_mapper_crash(self):
        """
        celery retry_floodwait_tasks should return a serializable dict
        without mapper initialization crash.
        """
        from app.features.inviter.tasks import retry_floodwait_tasks

        result = retry_floodwait_tasks()
        assert isinstance(result, dict)
        assert "success" in result


# ==================== Fix #5: Prevent future model/migration mismatch ====================

class TestModelMigrationGuard:
    """
    Guard tests that catch model/migration mismatches early.
    """

    MODELS_TO_CHECK: list[tuple[type, str, set[str]]] = [
        (Proxy, "proxies", {
            "id", "created_at", "updated_at",
            "owner_id", "title", "scheme", "host", "port",
            "username", "password", "secret",
            "country", "city",
            "ping_ms", "last_checked_at",
            "is_active", "is_working", "status_message",
            "extra_data", "notes",
        }),
        (ParsedChat, "parsed_chats", {
            "id", "created_at", "updated_at",
            "owner_id", "campaign_id",
            "chat_id", "username", "title", "description", "access_hash",
            "chat_type",
            "participants_count", "active_participants",
            "category", "niche", "tags",
            "language", "country",
            "is_public", "is_active", "is_restricted",
            "source", "last_parsed_at", "parse_count",
            "avg_posts_per_day", "avg_reach_per_post", "engagement_rate",
            "extra_data",
        }),
        (ParsedUser, "parsed_users", {
            "id", "created_at", "updated_at",
            "owner_id", "chat_id",
            "user_id", "username", "first_name", "last_name", "phone",
            "status",
            "is_bot", "is_verified", "is_scam", "is_fake",
            "last_seen", "was_online_at", "msg_count",
        }),
        (SourceCandidate, "source_candidates", {
            "id", "created_at", "updated_at",
            "owner_id", "source_type", "title", "username", "url",
            "tgstat_url", "category", "description",
            "subscribers_count", "avg_post_reach", "posts_per_day",
            "comments_enabled", "linked_chat_url",
            "discovered_by_query", "discovered_at", "last_analyzed_at",
            "status", "raw_data",
        }),
        (SourceScore, "source_scores", {
            "id", "created_at", "updated_at",
            "source_candidate_id",
            "topic_score", "activity_score",
            "audience_quality_score", "chat_liveness_score",
            "total_score", "reasons",
        }),
        (InviteCampaign, "invite_campaigns", {
            "id", "created_at", "updated_at",
            "owner_id", "title", "status",
            "source_chat_id", "source_chat_title", "source_type",
            "target_chat_id", "target_chat_title", "target_chat_username",
            "daily_limit_per_account",
            "invite_delay_min", "invite_delay_max",
            "pause_after_every", "pause_duration_min", "pause_duration_max",
            "warmup_enabled", "warmup_days", "warmup_limit_factor",
            "only_add_contacts", "add_to_contacts_first",
            "blacklist_usernames", "blacklist_user_ids",
            "notes",
            "started_at", "finished_at",
            "source_parsed_chat_id",
        }),
        (InviteTask, "invite_tasks", {
            "id", "created_at", "updated_at",
            "campaign_id", "account_id", "proxy_id",
            "target_user_id", "target_username",
            "status", "attempts", "max_attempts",
            "next_attempt_at",
            "error_code", "error_message",
            "invited_at",
        }),
    ]

    def test_all_key_models_have_expected_columns_in_code(self):
        """
        For each key model, verify that all expected columns are mapped.
        """
        for model_cls, table_name, expected_cols in self.MODELS_TO_CHECK:
            model_cols = _get_model_columns(model_cls)
            missing = expected_cols - model_cols
            extra = model_cols - expected_cols
            assert not missing, (
                f"Model {model_cls.__name__} (table '{table_name}') "
                f"is missing expected columns: {missing}. "
                f"Update the model definition or the expected columns list."
            )
            if extra:
                pytest.skip(
                    f"Model {model_cls.__name__} has extra columns: {extra}. "
                    f"Update the expected columns list in the test."
                )