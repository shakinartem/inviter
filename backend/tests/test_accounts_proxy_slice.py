from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts import api as accounts_api
from app.features.accounts.client_manager import TelegramClientManager
from app.features.accounts.models import Account
from app.features.accounts.schemas import AccountResponse
from app.features.accounts.service import AccountService
from app.features.proxies.candidate_models import ProxyCandidate
from app.features.proxies.candidate_service import CandidateService
from app.features.settings.models import SiteSettings


def _build_account(**overrides) -> Account:
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "label": "Main",
        "phone": "+15550000001",
        "session_name": "acc_main",
        "api_id": None,
        "api_hash": None,
        "status": "idle",
        "status_message": None,
        "is_active": True,
        "is_premium": False,
        "is_bot": False,
        "daily_invite_count": 0,
        "total_invites": 0,
        "total_invite_errors": 0,
        "total_floodwaits": 0,
        "success_rate": 0.0,
        "created_at": now,
        "updated_at": now,
        "extra_data": {"device_model": "Desktop"},
    }
    data.update(overrides)
    return Account(**data)


def _build_candidate(**overrides) -> ProxyCandidate:
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "proxy_type": "socks5",
        "host": "127.0.0.1",
        "port": 1080,
        "source_type": "manual_text",
        "status": "new",
        "score": 0,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return ProxyCandidate(**data)


@pytest.mark.asyncio
async def test_account_response_reads_extra_data_as_metadata() -> None:
    account = _build_account()

    response = AccountResponse.model_validate(account)

    assert response.metadata == {"device_model": "Desktop"}


@pytest.mark.asyncio
async def test_check_account_saves_profile_fields() -> None:
    session = AsyncMock(spec=AsyncSession)
    account = _build_account()
    client_manager = MagicMock()
    client_manager.session_exists.return_value = True
    client_manager.check_account = AsyncMock(
        return_value={
            "is_authorized": True,
            "status": "active",
            "status_message": "ok",
            "telegram_user_id": 777000,
            "username": "inviter_test",
            "first_name": "Invite",
            "last_name": "Tester",
            "phone": "+15550000099",
            "is_premium": True,
            "is_bot": False,
        }
    )

    service = AccountService(
        session=session,
        client_manager=client_manager,
    )
    service.get_account = AsyncMock(return_value=account)  # type: ignore[method-assign]
    service._apply_effective_telegram_credentials = AsyncMock()  # type: ignore[method-assign]

    result = await service.check_account(account.id)

    assert result["is_authorized"] is True
    assert account.telegram_user_id == 777000
    assert account.username == "inviter_test"
    assert account.first_name == "Invite"
    assert account.last_name == "Tester"
    assert account.phone == "+15550000099"
    assert account.is_premium is True
    assert account.is_bot is False
    assert account.status == "active"
    assert account.status_message == "ok"
    assert account.last_checked_at is not None
    assert account.last_seen_at is not None
    session.commit.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("premium_attr", ["premium", "is_premium"])
async def test_client_manager_check_account_supports_both_premium_attrs(
    premium_attr: str,
) -> None:
    manager = TelegramClientManager(redis=None)
    manager.disconnect_client = AsyncMock()
    me = SimpleNamespace(
        id=123456,
        username="premium_user",
        first_name="Premium",
        last_name="Member",
        phone="+15551112222",
        bot=False,
    )
    setattr(me, premium_attr, True)
    fake_client = SimpleNamespace(get_me=AsyncMock(return_value=me))
    manager.get_client = AsyncMock(return_value=fake_client)  # type: ignore[method-assign]
    account = SimpleNamespace(id=uuid4(), proxy_id=None)

    result = await manager.check_account(account)

    assert result["is_authorized"] is True
    assert result["is_premium"] is True
    manager.disconnect_client.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_account_missing_session_uses_friendly_message() -> None:
    session = AsyncMock(spec=AsyncSession)
    account = _build_account(session_name="missing_session")
    client_manager = MagicMock()
    client_manager.session_exists.return_value = False
    service = AccountService(session=session, client_manager=client_manager)
    service.get_account = AsyncMock(return_value=account)  # type: ignore[method-assign]

    with pytest.raises(FileNotFoundError) as exc_info:
        await service.check_account(account.id)

    assert (
        str(exc_info.value)
        == "Session file not found. Upload session or authorize account first."
    )


@pytest.mark.asyncio
async def test_check_account_endpoint_returns_friendly_400_for_missing_session() -> None:
    user = SimpleNamespace(id=uuid4())
    account = _build_account(owner_id=user.id)
    service = MagicMock()
    service.get_account = AsyncMock(return_value=account)
    service.check_account = AsyncMock(
        side_effect=FileNotFoundError(
            "Session file not found. Upload session or authorize account first."
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await accounts_api.check_account(
            account_id=account.id,
            current_user=user,
            service=service,
        )

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == "Session file not found. Upload session or authorize account first."
    )


@pytest.mark.asyncio
async def test_apply_effective_telegram_credentials_uses_global_settings() -> None:
    session = AsyncMock(spec=AsyncSession)
    site_settings = SiteSettings(
        system_config={
            "telegram_api": {
                "api_id": 12345,
                "api_hash": "0123456789abcdef0123456789abcdef",
            }
        }
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = site_settings
    session.execute.return_value = execute_result
    service = AccountService(session=session, client_manager=MagicMock())
    account = _build_account(api_id=None, api_hash=None)

    await service._apply_effective_telegram_credentials(account)

    assert account.api_id == 12345
    assert account.api_hash == "0123456789abcdef0123456789abcdef"


class _FakeWriter:
    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_check_candidate_timeout_marks_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = CandidateService(session)
    candidate = _build_candidate()

    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "open_connection", raise_timeout)

    result = await service.check_candidate(candidate)

    assert result.is_working is False
    assert candidate.status == "dead"
    assert candidate.last_error is not None
    assert "timeout" in candidate.last_error.lower()
    assert candidate.last_checked_at is not None


@pytest.mark.asyncio
async def test_check_candidate_exception_marks_dead_not_checking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = CandidateService(session)
    candidate = _build_candidate()

    async def raise_os_error(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(asyncio, "open_connection", raise_os_error)

    result = await service.check_candidate(candidate)

    assert result.is_working is False
    assert candidate.status == "dead"
    assert candidate.status != "checking"
    assert candidate.last_error is not None
    assert candidate.last_checked_at is not None


@pytest.mark.asyncio
async def test_check_candidate_success_marks_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = CandidateService(session)
    candidate = _build_candidate()

    async def open_connection(*args, **kwargs):
        return object(), _FakeWriter()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)

    result = await service.check_candidate(candidate)

    assert result.is_working is True
    assert candidate.status == "alive"
    assert candidate.latency_ms is not None
    assert candidate.last_error is None
    assert candidate.last_checked_at is not None


@pytest.mark.asyncio
async def test_bulk_check_candidates_does_not_commit_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_commits = 0

    async def guarded_commit():
        nonlocal active_commits
        active_commits += 1
        if active_commits > 1:
            raise AssertionError("commit used concurrently")
        await asyncio.sleep(0.001)
        active_commits -= 1

    session = AsyncMock(spec=AsyncSession)
    session.commit.side_effect = guarded_commit
    service = CandidateService(session)
    first = _build_candidate()
    second = _build_candidate(host="127.0.0.2", port=1081)
    candidates = {
        first.id: first,
        second.id: second,
    }

    async def get_candidate(candidate_id, owner_id):
        return candidates[candidate_id]

    async def open_connection(*args, **kwargs):
        await asyncio.sleep(0.002)
        return object(), _FakeWriter()

    monkeypatch.setattr(service, "get_candidate", get_candidate)
    monkeypatch.setattr(asyncio, "open_connection", open_connection)

    results = await service.bulk_check_candidates(
        ids=[first.id, second.id],
        owner_id=first.owner_id,
    )

    assert len(results) == 2
    assert {candidate.status for candidate in candidates.values()} == {"alive"}
