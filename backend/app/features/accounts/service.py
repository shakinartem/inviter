from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.client_manager import TelegramClientManager
from app.features.accounts.models import Account
from app.features.accounts.schemas import (
    AccountCreate,
    AccountListFilter,
    AccountStats,
    AccountStatusUpdate,
    AccountUpdate,
)
from app.features.proxies.models import Proxy


# Дневной лимит по умолчанию (если кампания не указала)
DEFAULT_DAILY_LIMIT = 30
# Время сброса дневного счётчика (UTC 00:00)
DAILY_RESET_HOUR_UTC = 0


class AccountService:
    """
    Сервис для управления Telegram-аккаунтами.
    Объединяет работу с БД, .session файлами, TelegramClientManager и Redis.
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: Optional[Redis] = None,
        client_manager: Optional[TelegramClientManager] = None,
    ) -> None:
        self.session = session
        self.redis = redis
        # Singleton: один TelegramClientManager на процесс
        self.client_manager = client_manager or TelegramClientManager(redis=redis)

    # ==================== CRUD ====================

    async def create_account(
        self, owner_id: UUID, account_in: AccountCreate
    ) -> Account:
        """Создать запись об аккаунте (без .session файла)."""
        session_name = account_in.session_name or f"acc_{secrets.token_hex(8)}"

        # Проверка уникальности session_name
        existing = await self.session.execute(
            select(Account.id).where(Account.session_name == session_name)
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"Account with session_name={session_name} already exists"
            )

        # Проверка уникальности phone
        if account_in.phone:
            existing_phone = await self.session.execute(
                select(Account.id).where(Account.phone == account_in.phone)
            )
            if existing_phone.scalar_one_or_none():
                raise ValueError(
                    f"Account with phone={account_in.phone} already exists"
                )

        account = Account(
            owner_id=owner_id,
            label=account_in.label,
            phone=account_in.phone,
            session_name=session_name,
            api_id=account_in.api_id,
            api_hash=account_in.api_hash,
            proxy_id=account_in.proxy_id,
            notes=account_in.notes,
            extra_data=account_in.metadata,
            status="idle",
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        logger.bind(
            account_id=str(account.id), session_name=session_name
        ).info("Account created")
        return account

    async def get_account(self, account_id: UUID) -> Optional[Account]:
        result = await self.session.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_accounts_by_ids(
        self, account_ids: Sequence[UUID], owner_id: Optional[UUID] = None
    ) -> List[Account]:
        """Получить несколько аккаунтов по списку ID. Опционально фильтр по владельцу."""
        if not account_ids:
            return []
        query = select(Account).where(Account.id.in_(list(account_ids)))
        if owner_id is not None:
            query = query.where(Account.owner_id == owner_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_accounts(
        self,
        owner_id: UUID,
        filters: AccountListFilter,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Account]:
        query = select(Account).where(Account.owner_id == owner_id)

        if filters.status:
            query = query.where(Account.status == filters.status)
        if filters.is_active is not None:
            query = query.where(Account.is_active == filters.is_active)
        if filters.proxy_id:
            query = query.where(Account.proxy_id == filters.proxy_id)
        if filters.is_premium is not None:
            query = query.where(Account.is_premium == filters.is_premium)
        if filters.search:
            term = f"%{filters.search}%"
            query = query.where(
                or_(
                    Account.label.ilike(term),
                    Account.phone.ilike(term),
                    Account.username.ilike(term),
                )
            )

        query = (
            query.order_by(Account.created_at.desc()).offset(skip).limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_account(
        self, account_id: UUID, account_in: AccountUpdate
    ) -> Optional[Account]:
        account = await self.get_account(account_id)
        if not account:
            return None
        update_dict = account_in.model_dump(exclude_unset=True)
        metadata = update_dict.pop("metadata", None) if "metadata" in update_dict else None
        for key, value in update_dict.items():
            setattr(account, key, value)
        if "metadata" in account_in.model_fields_set:
            account.extra_data = metadata
        await self.session.commit()
        await self.session.refresh(account)
        logger.bind(account_id=str(account_id)).info("Account updated")
        return account

    async def update_status(
        self, account_id: UUID, status_in: AccountStatusUpdate
    ) -> Optional[Account]:
        account = await self.get_account(account_id)
        if not account:
            return None
        account.status = status_in.status
        if status_in.status_message is not None:
            account.status_message = status_in.status_message
        if status_in.cooldown_until is not None:
            account.cooldown_until = status_in.cooldown_until
        if status_in.banned_until is not None:
            account.banned_until = status_in.banned_until
        account.last_checked_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def delete_account(self, account_id: UUID) -> bool:
        """Удалить аккаунт из БД + .session файл + отключить клиент."""
        account = await self.get_account(account_id)
        if not account:
            return False

        session_name = account.session_name

        # Сначала отключаем клиент
        try:
            await self.client_manager.invalidate_client(account.id)
        except Exception as e:
            logger.bind(account_id=str(account_id)).warning(
                f"Failed to invalidate client during delete: {e}"
            )

        # Удаляем из Redis (daily counter, floodwait, status)
        if self.redis is not None:
            try:
                keys = [
                    f"account:{account.id}:status",
                    f"account:daily_invites:{account.id}",
                    f"account:floodwait:{account.id}",
                ]
                await self.redis.delete(*keys)
            except Exception as e:
                logger.bind(account_id=str(account_id)).warning(
                    f"Failed to cleanup redis on delete: {e}"
                )

        await self.session.delete(account)
        await self.session.commit()

        # Удаляем .session файл
        self.client_manager.delete_session_file(session_name)
        logger.bind(
            account_id=str(account_id), session_name=session_name
        ).info("Account deleted")
        return True

    # ==================== Session operations ====================

    async def upload_session(
        self, account_id: UUID, session_bytes: bytes
    ) -> Account:
        """
        Сохранить .session файл для существующего аккаунта.
        Валидирует формат и инвалидирует старый клиент.
        """
        account = await self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not session_bytes:
            raise ValueError("Empty session data")

        # sanity-проверка: Telethon .session — sqlite3
        if not session_bytes.startswith(b"SQLite format 3"):
            raise ValueError(
                "Invalid .session file: expected SQLite format. "
                "Make sure you uploaded a real Telethon session."
            )

        # Перед заменой — отключаем старый клиент (если был закэширован)
        try:
            await self.client_manager.invalidate_client(account.id)
        except Exception:
            pass

        self.client_manager.save_session_bytes(
            account.session_name, session_bytes
        )
        account.last_checked_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def check_account(self, account_id: UUID) -> dict:
        """
        Проверить авторизацию аккаунта.
        Обновляет профиль (username, first_name и т.д.) и метрики.
        """
        account = await self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        if not self.client_manager.session_exists(account.session_name):
            raise FileNotFoundError(
                f"Session file not found for {account.session_name}. "
                "Upload it first."
            )

        proxy = None
        if account.proxy_id:
            proxy = await self._get_proxy(account.proxy_id)

        result = await self.client_manager.check_account(account)

        # обновляем профиль и метрики в БД
        if result.get("telegram_user_id"):
            account.telegram_user_id = result["telegram_user_id"]
        if result.get("username") is not None:
            account.username = result["username"]
        if result.get("first_name") is not None:
            account.first_name = result["first_name"]
        if result.get("last_name") is not None:
            account.last_name = result["last_name"]
        account.is_premium = result.get("is_premium", False)
        account.is_bot = result.get("is_bot", False)
        new_status = result.get("status", "error")
        account.status = new_status
        if result.get("status_message"):
            account.status_message = result["status_message"]
        account.last_seen_at = datetime.now(timezone.utc)

        # Если аккаунт только что стал активным — сбрасываем banned/cooldown
        if new_status == "active":
            account.banned_until = None
            account.cooldown_until = None

        # Если забанен — ставим дефолтный banned_until (24ч)
        if new_status == "banned" and not account.banned_until:
            account.banned_until = datetime.now(timezone.utc) + timedelta(hours=24)

        await self.session.commit()
        await self.session.refresh(account)
        return result

    # ==================== Bulk operations ====================

    async def bulk_update_status(
        self,
        account_ids: Sequence[UUID],
        owner_id: UUID,
        new_status: str,
        status_message: Optional[str] = None,
    ) -> int:
        """Массовое обновление статуса. Возвращает количество обновлённых."""
        if not account_ids:
            return 0
        stmt = (
            update(Account)
            .where(
                and_(
                    Account.id.in_(list(account_ids)),
                    Account.owner_id == owner_id,
                )
            )
            .values(
                status=new_status,
                status_message=status_message,
                last_checked_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        # инвалидируем клиенты
        await self.client_manager.bulk_invalidate(list(account_ids))
        logger.bind(
            count=result.rowcount, new_status=new_status, owner_id=str(owner_id)
        ).info("Bulk status update")
        return int(result.rowcount or 0)

    async def bulk_delete(
        self, account_ids: Sequence[UUID], owner_id: UUID
    ) -> int:
        """Массовое удаление аккаунтов. Возвращает количество удалённых."""
        if not account_ids:
            return 0
        # сначала отключаем клиентов
        await self.client_manager.bulk_invalidate(list(account_ids))
        # затем удаляем
        stmt = (
            update(Account)
            .where(
                and_(
                    Account.id.in_(list(account_ids)),
                    Account.owner_id == owner_id,
                )
            )
            .values(is_active=False, status="inactive")
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return int(result.rowcount or 0)

    # ==================== Daily counter / rate limit ====================

    async def _maybe_reset_daily_counter(self, account: Account) -> None:
        """Сбрасывает дневной счётчик, если подошло время (UTC 00:00)."""
        now = datetime.now(timezone.utc)
        last_reset = account.daily_invite_reset_at
        if last_reset is None or last_reset.date() < now.date():
            account.daily_invite_count = 0
            account.daily_invite_reset_at = now
            if self.redis is not None:
                await self.client_manager.reset_daily_invites(account.id)

    async def get_today_invites(
        self, account_id: UUID
    ) -> int:
        """
        Сколько инвайтов аккаунт отправил сегодня.
        Приоритет: Redis (быстрее), fallback в БД.
        """
        if self.redis is not None:
            value = await self.client_manager.get_daily_invites(account_id)
            if value:
                return value
        # fallback в БД
        result = await self.session.execute(
            select(Account.daily_invite_count).where(Account.id == account_id)
        )
        return int(result.scalar() or 0)

    async def increment_invite_counter(self, account_id: UUID) -> None:
        """Инкремент счётчика приглашений (Redis + БД)."""
        account = await self.get_account(account_id)
        if not account:
            return
        await self._maybe_reset_daily_counter(account)
        account.daily_invite_count = (account.daily_invite_count or 0) + 1
        account.total_invites = (account.total_invites or 0) + 1
        account.last_used_at = datetime.now(timezone.utc)
        if self.redis is not None:
            await self.client_manager.increment_daily_invites(account_id)
        await self.session.commit()
        await self.session.refresh(account)

    async def record_invite_error(
        self, account_id: UUID, error_code: Optional[str] = None
    ) -> None:
        """Записать ошибку инвайта (для метрик)."""
        account = await self.get_account(account_id)
        if not account:
            return
        account.total_invite_errors = (account.total_invite_errors or 0) + 1
        # success_rate = success / (success + errors)
        total = (account.total_invites or 0) + (account.total_invite_errors or 0)
        if total > 0:
            account.success_rate = round(
                (account.total_invites or 0) / total, 4
            )
        if error_code and "FLOOD" in error_code.upper():
            account.total_floodwaits = (account.total_floodwaits or 0) + 1
        await self.session.commit()

    async def can_account_invite(
        self,
        account_id: UUID,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
    ) -> tuple[bool, Optional[str]]:
        """
        Проверить, может ли аккаунт отправить инвайт сейчас.
        Возвращает (allowed, reason).
        """
        account = await self.get_account(account_id)
        if not account:
            return False, "Account not found"
        if not account.is_active:
            return False, "Account is inactive"
        if account.status == "banned":
            return False, "Account is banned"
        if account.status == "inactive":
            return False, "Account is inactive"
        if account.status == "cooldown":
            if account.cooldown_until and account.cooldown_until > datetime.now(
                timezone.utc
            ):
                remaining = int(
                    (account.cooldown_until - datetime.now(timezone.utc)).total_seconds()
                )
                return False, f"Cooldown active for {remaining}s"
        # Floodwait в Redis
        if self.redis is not None:
            fw = await self.client_manager.get_floodwait_remaining(account_id)
            if fw > 0:
                return False, f"Floodwait for {fw}s"
        # Дневной лимит
        await self._maybe_reset_daily_counter(account)
        if account.daily_invite_count >= daily_limit:
            return False, f"Daily limit reached ({daily_limit})"
        return True, None

    # ==================== Active / available ====================

    async def get_active_accounts(
        self, owner_id: Optional[UUID] = None
    ) -> List[Account]:
        """Список активных аккаунтов (для кампаний)."""
        query = select(Account).where(
            and_(
                Account.is_active == True,  # noqa: E712
                Account.status.notin_(["banned", "inactive"]),
            )
        )
        if owner_id is not None:
            query = query.where(Account.owner_id == owner_id)
        query = query.order_by(Account.last_used_at.asc().nulls_first())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_available_for_invite(
        self, owner_id: UUID, daily_limit: int = DEFAULT_DAILY_LIMIT
    ) -> List[Account]:
        """Аккаунты, которые МОГУТ инвайтить прямо сейчас (без cooldown/banned/limit)."""
        active = await self.get_active_accounts(owner_id=owner_id)
        available: List[Account] = []
        for account in active:
            can, _reason = await self.can_account_invite(account.id, daily_limit)
            if can:
                available.append(account)
        return available

    # ==================== Stats ====================

    async def get_stats(self, owner_id: UUID) -> AccountStats:
        """Получить сводную статистику по аккаунтам владельца."""
        now = datetime.now(timezone.utc)

        total = await self._count_accounts(owner_id)
        active = await self._count_accounts(owner_id, status="active")
        banned = await self._count_accounts(owner_id, status="banned")
        limited = await self._count_accounts(owner_id, status="limited")
        cooldown = await self._count_accounts(owner_id, status="cooldown")
        inactive = await self._count_accounts(owner_id, status="inactive")

        # in_cooldown_now
        in_cooldown = await self.session.execute(
            select(func.count(Account.id)).where(
                and_(
                    Account.owner_id == owner_id,
                    Account.cooldown_until.is_not(None),
                    Account.cooldown_until > now,
                )
            )
        )
        in_cooldown_now = in_cooldown.scalar() or 0

        # premium
        premium = await self.session.execute(
            select(func.count(Account.id)).where(
                and_(
                    Account.owner_id == owner_id,
                    Account.is_premium == True,  # noqa: E712
                )
            )
        )
        premium_count = premium.scalar() or 0

        # invites today (из Redis или БД)
        total_invites_today = 0
        if self.redis is not None:
            # Суммируем по всем аккаунтам владельца
            result = await self.session.execute(
                select(Account.id).where(Account.owner_id == owner_id)
            )
            for (acc_id,) in result.all():
                total_invites_today += await self.client_manager.get_daily_invites(
                    acc_id
                )
        else:
            invites_today = await self.session.execute(
                select(
                    func.coalesce(func.sum(Account.daily_invite_count), 0)
                ).where(Account.owner_id == owner_id)
            )
            total_invites_today = int(invites_today.scalar() or 0)

        # avg success rate
        avg_rate = await self.session.execute(
            select(func.coalesce(func.avg(Account.success_rate), 0.0)).where(
                Account.owner_id == owner_id
            )
        )
        avg_success_rate = float(avg_rate.scalar() or 0.0)

        return AccountStats(
            total=total,
            active=active,
            banned=banned,
            limited=limited,
            cooldown=cooldown,
            inactive=inactive,
            in_cooldown_now=in_cooldown_now,
            premium_count=premium_count,
            total_invites_today=total_invites_today,
            avg_success_rate=round(avg_success_rate, 2),
        )

    async def get_detailed_stats(self, account_id: UUID) -> dict:
        """Подробная статистика по одному аккаунту."""
        account = await self.get_account(account_id)
        if not account:
            return {}
        today = await self.get_today_invites(account_id)
        floodwait_remaining = 0
        if self.redis is not None:
            floodwait_remaining = await self.client_manager.get_floodwait_remaining(
                account_id
            )
        return {
            "account_id": str(account_id),
            "status": account.status,
            "is_active": account.is_active,
            "is_premium": account.is_premium,
            "daily_invite_count": today,
            "total_invites": account.total_invites or 0,
            "total_invite_errors": account.total_invite_errors or 0,
            "total_floodwaits": account.total_floodwaits or 0,
            "success_rate": account.success_rate or 0.0,
            "floodwait_remaining": floodwait_remaining,
            "last_used_at": account.last_used_at,
            "last_checked_at": account.last_checked_at,
            "cooldown_until": account.cooldown_until,
            "banned_until": account.banned_until,
            "session_exists": self.client_manager.session_exists(
                account.session_name
            ),
            "session_size": self.client_manager.get_session_file_size(
                account.session_name
            ),
        }

    async def _count_accounts(
        self, owner_id: UUID, status: Optional[str] = None
    ) -> int:
        query = select(func.count(Account.id)).where(
            Account.owner_id == owner_id
        )
        if status:
            query = query.where(Account.status == status)
        result = await self.session.execute(query)
        return int(result.scalar() or 0)

    async def _get_proxy(self, proxy_id: UUID) -> Optional[Proxy]:
        result = await self.session.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        return result.scalar_one_or_none()

    # ==================== Client helpers ====================

    async def get_or_create_client(self, account_id: UUID):
        """
        Получить Telethon-клиент для аккаунта.
        """
        from telethon import TelegramClient  # noqa: F401

        account = await self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        proxy = None
        if account.proxy_id:
            proxy = await self._get_proxy(account.proxy_id)

        account.last_used_at = datetime.now(timezone.utc)
        await self.session.commit()
        return await self.client_manager.get_client(account, proxy)
