"""Tests for Parser → InviteCampaign → InviteTask pipeline."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.inviter.models import InviteCampaign, InviteTask
from app.features.inviter.schemas import (
    InviteCampaignCreate,
    InviteSettings,
    InviteTaskCreate,
)
from app.features.inviter.service import InviterService
from app.features.parser.models import ParsedChat, ParsedUser
from app.features.accounts.models import Account


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Create a mock Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_telegram_client_manager():
    """Create a mock TelegramClientManager."""
    manager = MagicMock()
    manager.get_client = AsyncMock()
    manager.release_client = AsyncMock()
    return manager


@pytest.fixture
def service(mock_session, mock_telegram_client_manager, mock_redis):
    """Create InviterService with mocked dependencies."""
    return InviterService(mock_session, mock_telegram_client_manager, mock_redis)


class TestGetTargetUsers:
    """Tests for _get_target_users method."""

    @pytest.mark.asyncio
    async def test_parsed_list_source_empty(self, service, mock_session):
        """When source_type=parsed_list but no parsed_users, return empty list."""
        # Arrange
        campaign = InviteCampaign(
            id=uuid4(),
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=uuid4(),
            target_chat_id=12345,
        )

        # Mock: no ParsedUser records for this chat
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Act
        users = await service._get_target_users(campaign)

        # Assert
        assert users == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_parsed_list_source_with_users(self, service, mock_session):
        """When source_type=parsed_list with parsed_users, return them."""
        # Arrange
        parsed_chat_id = uuid4()
        campaign = InviteCampaign(
            id=uuid4(),
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=parsed_chat_id,
            target_chat_id=12345,
        )

        # Mock ParsedUser records
        user1 = MagicMock(spec=ParsedUser)
        user1.user_id = 111
        user1.username = "user1"
        user1.is_bot = False
        user1.is_scam = False
        user1.is_fake = False

        user2 = MagicMock(spec=ParsedUser)
        user2.user_id = 222
        user2.username = None
        user2.is_bot = False
        user2.is_scam = False
        user2.is_fake = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [user1, user2]
        mock_session.execute.return_value = mock_result

        # Act
        users = await service._get_target_users(campaign)

        # Assert
        assert len(users) == 2
        assert users[0]["user_id"] == 111
        assert users[0]["username"] == "user1"
        assert users[1]["user_id"] == 222
        assert users[1]["username"] is None

    @pytest.mark.asyncio
    async def test_parsed_list_filters_bots_scam_fake(self, service, mock_session):
        """Should filter out bots, scam and fake users."""
        # Arrange
        parsed_chat_id = uuid4()
        campaign = InviteCampaign(
            id=uuid4(),
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=parsed_chat_id,
            target_chat_id=12345,
        )

        good_user = MagicMock(spec=ParsedUser)
        good_user.user_id = 111
        good_user.username = "good_user"
        good_user.is_bot = False
        good_user.is_scam = False
        good_user.is_fake = False

        bot_user = MagicMock(spec=ParsedUser)
        bot_user.user_id = 222
        bot_user.username = "bot_user"
        bot_user.is_bot = True
        bot_user.is_scam = False
        bot_user.is_fake = False

        scam_user = MagicMock(spec=ParsedUser)
        scam_user.user_id = 333
        scam_user.username = "scam_user"
        scam_user.is_bot = False
        scam_user.is_scam = True
        scam_user.is_fake = False

        fake_user = MagicMock(spec=ParsedUser)
        fake_user.user_id = 444
        fake_user.username = "fake_user"
        fake_user.is_bot = False
        fake_user.is_scam = False
        fake_user.is_fake = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            good_user, bot_user, scam_user, fake_user
        ]
        mock_session.execute.return_value = mock_result

        # Act
        users = await service._get_target_users(campaign)

        # Assert
        assert len(users) == 1
        assert users[0]["user_id"] == 111
        assert users[0]["username"] == "good_user"

    @pytest.mark.asyncio
    async def test_default_source_returns_empty(self, service, mock_session):
        """When source_type=chat without source_chat_id, return empty list."""
        campaign = InviteCampaign(
            id=uuid4(),
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="chat",
            target_chat_id=12345,
        )

        users = await service._get_target_users(campaign)
        assert users == []


class TestPrepareTasks:
    """Tests for prepare_tasks_for_campaign method."""

    @pytest.mark.asyncio
    async def test_create_tasks_from_target_users(self, service, mock_session):
        """Should create InviteTask for each target user."""
        # Arrange
        campaign_id = uuid4()
        account_id = uuid4()
        campaign = InviteCampaign(
            id=campaign_id,
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=uuid4(),
            target_chat_id=12345,
        )

        account = MagicMock(spec=Account)
        account.id = account_id
        account.created_at = datetime.utcnow()

        target_users = [
            {"user_id": 111, "username": "user1"},
            {"user_id": 222, "username": "user2"},
            {"user_id": 333, "username": "user3"},
        ]

        settings = InviteSettings(
            daily_limit_per_account=50,
            invite_delay_min=30,
            invite_delay_max=60,
            pause_after_every=10,
            pause_duration_min=5,
            pause_duration_max=10,
        )

        # Mock _get_account_daily_limit to return 50
        # We need to patch the async method
        with patch.object(
            service, "_get_account_daily_limit", new_callable=AsyncMock
        ) as mock_limit:
            mock_limit.return_value = 50

            # Act
            created = await service.prepare_tasks_for_campaign(
                campaign, [account], target_users, settings
            )

        # Assert
        assert created == 3
        # _create_task called 3 times
        assert mock_session.add.call_count == 3
        assert mock_session.commit.call_count == 3  # 3 tasks * 1 commit each

    @pytest.mark.asyncio
    async def test_skip_blacklisted_users(self, service, mock_session):
        """Should skip users in blacklist when creating tasks."""
        # Arrange
        campaign_id = uuid4()
        account_id = uuid4()
        campaign = InviteCampaign(
            id=campaign_id,
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=uuid4(),
            target_chat_id=12345,
        )

        account = MagicMock(spec=Account)
        account.id = account_id
        account.created_at = datetime.utcnow()

        target_users = [
            {"user_id": 111, "username": "user1"},
            {"user_id": 222, "username": "blacklisted_user"},  # in blacklist
            {"user_id": 333, "username": "user3"},
        ]

        settings = InviteSettings(
            daily_limit_per_account=50,
            invite_delay_min=30,
            invite_delay_max=60,
            pause_after_every=10,
            pause_duration_min=5,
            pause_duration_max=10,
            blacklist_usernames=["blacklisted_user"],
            blacklist_user_ids=[],
        )

        with patch.object(
            service, "_get_account_daily_limit", new_callable=AsyncMock
        ) as mock_limit:
            mock_limit.return_value = 50

            # Act
            created = await service.prepare_tasks_for_campaign(
                campaign, [account], target_users, settings
            )

        # Assert
        assert created == 2  # one user skipped
        assert mock_session.add.call_count == 2
        assert mock_session.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_no_duplicate_tasks_check(self, service, mock_session):
        """
        Ensure we do not create duplicate InviteTask for the same campaign user.
        """
        # Arrange
        campaign_id = uuid4()
        account_id = uuid4()
        campaign = InviteCampaign(
            id=campaign_id,
            owner_id=uuid4(),
            title="Test Campaign",
            source_type="parsed_list",
            source_parsed_chat_id=uuid4(),
            target_chat_id=12345,
        )

        account = MagicMock(spec=Account)
        account.id = account_id
        account.created_at = datetime.utcnow()

        # Same user listed twice
        target_users = [
            {"user_id": 111, "username": "user1"},
            {"user_id": 111, "username": "user1"},
        ]

        settings = InviteSettings(
            daily_limit_per_account=50,
        )

        with patch.object(
            service, "_get_account_daily_limit", new_callable=AsyncMock
        ) as mock_limit:
            mock_limit.return_value = 50

            # Act
            created = await service.prepare_tasks_for_campaign(
                campaign, [account], target_users, settings
            )

        assert created == 1
        assert mock_session.add.call_count == 1
