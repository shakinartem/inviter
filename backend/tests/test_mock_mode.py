from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.accounts.service import AccountService
from app.features.inviter.models import InviteCampaign, InviteTask
from app.features.inviter.service import InviterService
from app.features.parser.service import ParserService


@pytest.mark.asyncio
async def test_mock_account_check_marks_account_active() -> None:
    session = AsyncMock(spec=AsyncSession)
    account = Account(
        id=uuid4(),
        owner_id=uuid4(),
        label="Mock Account",
        phone="+15550000001",
        session_name="mock_account",
        status="idle",
    )
    service = AccountService(session=session, client_manager=MagicMock())
    service.get_account = AsyncMock(return_value=account)  # type: ignore[method-assign]

    with patch("app.features.accounts.service.settings.telegram_mock_mode", True):
        result = await service.check_account(account.id)

    assert result["is_authorized"] is True
    assert result["status"] == "active"
    assert result["username"].startswith("mock_")
    assert account.status == "active"
    assert account.telegram_user_id is not None
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_mock_parser_creates_parsed_chat_and_users() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = ParserService()

    chat = await service.create_mock_parsed_users(
        owner_id=uuid4(),
        db_session=session,
        title="Mock Audience",
        count=3,
        username_prefix="lead",
    )

    assert chat.title == "Mock Audience"
    assert chat.source == "manual"
    assert chat.participants_count == 3
    assert session.add.call_count == 4
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_mock_invite_task_becomes_success_and_creates_log() -> None:
    session = AsyncMock(spec=AsyncSession)
    service = InviterService(session, MagicMock(), AsyncMock())
    task = InviteTask(
        id=uuid4(),
        campaign_id=uuid4(),
        account_id=uuid4(),
        target_user_id=1001,
        target_username="lead_1",
        status="pending",
    )
    campaign = InviteCampaign(
        id=task.campaign_id,
        owner_id=uuid4(),
        title="Mock Campaign",
        source_type="parsed_list",
        target_chat_id=-100123,
    )
    account = SimpleNamespace(id=task.account_id, created_at=datetime.utcnow())

    service._get_task = AsyncMock(return_value=task)  # type: ignore[method-assign]
    service.get_campaign = AsyncMock(return_value=campaign)  # type: ignore[method-assign]
    service._get_account = AsyncMock(return_value=account)  # type: ignore[method-assign]
    service.can_account_invite = AsyncMock(return_value=True)  # type: ignore[method-assign]
    service._increment_daily_invite_count = AsyncMock()  # type: ignore[method-assign]

    with patch("app.features.inviter.service.settings.telegram_mock_mode", True):
        result = await service.execute_invite_task(task.id)

    assert result["success"] is True
    assert task.status == "success"
    assert task.invited_at is not None
    assert any(
        call.args[0].action == "mock_invite" and call.args[0].success is True
        for call in session.add.call_args_list
    )
