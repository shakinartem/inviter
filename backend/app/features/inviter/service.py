from __future__ import annotations

import random
import inspect
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.inviter.models import InviteCampaign, InviteTask, InviteLog
from app.features.inviter.schemas import (
    InviteCampaignCreate,
    InviteCampaignUpdate,
    InviteSettings,
    InviteTaskCreate,
    StartCampaignRequest,
    CampaignStats,
)
from app.features.accounts.models import Account
from app.core.config import settings as app_settings
from app.features.proxies.models import Proxy
from app.features.parser.models import ParsedChat, ParsedUser
from app.features.telegram.client_manager import TelegramClientManager
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError,
    PeerFloodError,
    ChatAdminRequiredError,
    ChannelPrivateError,
    UserBannedInChannelError,
    InviteRequestSentError,
    UserIsBlockedError,
    ChatWriteForbiddenError,
)

settings = app_settings


class InviterService:
    """
    Сервис для управления кампаниями инвайтинга и связанными операциями.
    Инкапсулирует бизнес-логику работы с кампаниями, задачами и логами.
    """

    def __init__(
        self,
        session: AsyncSession,
        telegram_client_manager: TelegramClientManager,
        redis: Redis,
    ):
        self.session = session
        self.telegram_client_manager = telegram_client_manager
        self.redis = redis

    # ==================== Campaign Methods ====================

    async def create_campaign(
        self, campaign_in: InviteCampaignCreate, owner_id: UUID
    ) -> InviteCampaign:
        """
        Создать новую кампанию инвайтинга.
        """
        campaign_dict = campaign_in.model_dump()
        settings = campaign_dict.pop("settings")
        # Объединяем настройки с основными полями кампании
        campaign_dict.update(settings.model_dump())

        campaign = InviteCampaign(owner_id=owner_id, **campaign_dict)
        self.session.add(campaign)
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def get_campaign(self, campaign_id: UUID) -> Optional[InviteCampaign]:
        """
        Получить кампанию по ID.
        """
        result = await self.session.execute(
            select(InviteCampaign).where(InviteCampaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_campaigns(
        self, owner_id: UUID, filters: dict, skip: int = 0, limit: int = 100
    ) -> List[InviteCampaign]:
        """
        Получить список кампаний с фильтрацией и пагинацией.
        """
        query = select(InviteCampaign).where(InviteCampaign.owner_id == owner_id)

        if filters.get("status"):
            query = query.where(InviteCampaign.status == filters["status"])
        if filters.get("search"):
            query = query.where(InviteCampaign.title.ilike(f"%{filters['search']}%"))
        if filters.get("created_after"):
            query = query.where(InviteCampaign.created_at >= filters["created_after"])
        if filters.get("created_before"):
            query = query.where(InviteCampaign.created_at <= filters["created_before"])

        query = query.order_by(InviteCampaign.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_campaign(
        self, campaign_id: UUID, campaign_in: InviteCampaignUpdate
    ) -> Optional[InviteCampaign]:
        """
        Обновить кампанию.
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        update_dict = campaign_in.model_dump(exclude_unset=True)
        settings = update_dict.pop("settings", None)
        if settings:
            update_dict.update(settings)

        for key, value in update_dict.items():
            setattr(campaign, key, value)

        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def delete_campaign(self, campaign_id: UUID) -> bool:
        """
        Удалить кампанию.
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False

        await self.session.delete(campaign)
        await self.session.commit()
        return True

    async def get_campaign_tasks(
        self,
        campaign_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[InviteTask]:
        """
        Получить список задач кампании с фильтрацией по статусу.
        """
        query = select(InviteTask).where(InviteTask.campaign_id == campaign_id)
        if status:
            query = query.where(InviteTask.status == status)
        query = query.order_by(InviteTask.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_task_logs(
        self, task_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[InviteLog]:
        """
        Получить логи задачи.
        """
        query = (
            select(InviteLog)
            .where(InviteLog.invite_task_id == task_id)
            .order_by(InviteLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_task(self, task_in: InviteTaskCreate) -> InviteTask:
        """
        Создать задачу инвайтинга.
        """
        return await self._create_task(task_in)

    async def start_campaign(self, campaign_id: UUID, user_id: UUID) -> dict:
        """
        Запуск кампании (проверка прав, создание задач, запуск Celery task).
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return {"success": False, "message": "Кампания не найдена"}

        # Проверяем права владельца
        if campaign.owner_id != user_id:
            return {"success": False, "message": "Недостаточно прав"}

        if campaign.status != "draft":
            return {
                "success": False,
                "message": f"Кампания должна быть в статусе черновика для запуска. Текущий статус: {campaign.status}",
            }

        # Получаем настройки кампании
        settings = await self._get_effective_settings(campaign)

        # Получаем список доступных аккаунтов
        accounts = await self._get_available_accounts(campaign, settings)
        if not accounts:
            return {"success": False, "message": "Нет доступных аккаунтов для запуска кампании"}

        # Получаем список пользователей для приглашения
        target_users = await self._get_target_users(campaign)
        if not target_users:
            return {"success": False, "message": "Не найдено пользователей для приглашения"}

        # Создаем задачи
        tasks_created = await self.prepare_tasks_for_campaign(
            campaign, accounts, target_users, settings
        )

        # Обновляем статус кампании
        campaign.status = "active"
        campaign.started_at = datetime.utcnow()
        await self.session.commit()

        if app_settings.telegram_mock_mode and tasks_created > 0:
            pending_tasks = await self.get_campaign_tasks(
                campaign_id=campaign.id,
                status="pending",
                skip=0,
                limit=tasks_created,
            )
            for task in pending_tasks:
                await self.execute_invite_task(task.id)

        # В реальной реализации здесь нужно запучить Celery задачи для обработки кампании
        # Например: process_campaign_tasks.delay(campaign_id)

        return {
            "success": True,
            "message": f"Кампания запущена. Создано задач: {tasks_created}",
            "tasks_created": tasks_created,
        }

    async def pause_campaign(self, campaign_id: UUID) -> bool:
        """
        Поставить кампанию на паузу.
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False

        campaign.status = "paused"
        await self.session.commit()
        return True

    async def stop_campaign(self, campaign_id: UUID) -> bool:
        """
        Остановить кампанию.
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False

        campaign.status = "completed"
        campaign.finished_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def get_campaign_stats(self, campaign_id: UUID) -> CampaignStats:
        """
        Получить статистику кампании.
        """
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return CampaignStats(
                campaign_id=campaign_id,
                title="",
                status="draft",
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                floodwait_tasks=0,
                success_rate=0.0,
                started_at=None,
                finished_at=None,
                invites_today=0,
                active_accounts=0,
            )

        # Подсчитываем задачи по статусам
        total_result = await self.session.execute(
            select(func.count(InviteTask.id)).where(InviteTask.campaign_id == campaign_id)
        )
        total_tasks = total_result.scalar()

        success_result = await self.session.execute(
            select(func.count(InviteTask.id))
            .where(
                and_(
                    InviteTask.campaign_id == campaign_id,
                    InviteTask.status == "success",
                )
            )
        )
        success_tasks = success_result.scalar()

        failed_result = await self.session.execute(
            select(func.count(InviteTask.id))
            .where(
                and_(
                    InviteTask.campaign_id == campaign_id,
                    InviteTask.status == "failed",
                )
            )
        )
        failed_tasks = failed_result.scalar()

        floodwait_result = await self.session.execute(
            select(func.count(InviteTask.id))
            .where(
                and_(
                    InviteTask.campaign_id == campaign_id,
                    InviteTask.status == "floodwait",
                )
            )
        )
        floodwait_tasks = floodwait_result.scalar()

        success_rate = (
            (success_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
        )

        # Подсчитываем приглашения за сегодня
        today = datetime.utcnow().date()
        today_result = await self.session.execute(
            select(func.count(InviteTask.id))
            .where(
                and_(
                    InviteTask.campaign_id == campaign_id,
                    InviteTask.invited_at >= today,
                    InviteTask.status == "success",
                )
            )
        )
        invites_today = today_result.scalar()

        # Подсчитываем активные аккаунты
        active_accounts_result = await self.session.execute(
            select(func.count(func.distinct(InviteTask.account_id)))
            .where(
                and_(
                    InviteTask.campaign_id == campaign_id,
                    InviteTask.status.in_(["pending", "processing"]),
                )
            )
        )
        active_accounts = active_accounts_result.scalar()

        return CampaignStats(
            campaign_id=campaign.id,
            title=campaign.title,
            status=campaign.status,
            total_tasks=total_tasks,
            completed_tasks=success_tasks,
            failed_tasks=failed_tasks,
            floodwait_tasks=floodwait_tasks,
            success_rate=round(success_rate, 2),
            started_at=campaign.started_at,
            finished_at=campaign.finished_at,
            invites_today=invites_today,
            active_accounts=active_accounts,
        )

    # ==================== Task Methods ====================

    async def prepare_tasks_for_campaign(
        self,
        campaign: InviteCampaign,
        accounts: List[Account],
        target_users: List[dict],
        settings: InviteSettings,
    ) -> int:
        """
        Создание InviteTask из source_chat.
        Возвращает количество созданных задач.
        """
        tasks_created = 0
        user_index = 0
        seen_user_ids: set[int] = set()
        existing_user_ids = await self._get_existing_task_user_ids(campaign.id)

        for account in accounts:
            # Вычисляем текущий дневной лимит аккаунта с учётом warmup
            daily_limit = await self._get_account_daily_limit(account, settings)

            # Назначаем пользователей аккаунту
            while (
                user_index < len(target_users)
                and tasks_created < daily_limit * len(accounts)
            ):
                target_user = target_users[user_index]
                target_user_id = int(target_user["user_id"])
                if target_user_id in seen_user_ids or target_user_id in existing_user_ids:
                    user_index += 1
                    continue
                seen_user_ids.add(target_user_id)

                # Проверяем черные списки
                if await self._is_user_blacklisted(target_user, settings):
                    user_index += 1
                    continue

                # Создаем задачу
                task_data = InviteTaskCreate(
                    campaign_id=campaign.id,
                    account_id=account.id,
                    proxy_id=None,  # В реальной реализации нужно назначать прокси
                    target_user_id=target_user_id,
                    target_username=target_user.get("username"),
                )
                await self._create_task(task_data)
                tasks_created += 1
                user_index += 1

        return tasks_created

    async def _get_existing_task_user_ids(self, campaign_id: UUID) -> set[int]:
        try:
            result = await self.session.execute(
                select(InviteTask.target_user_id).where(InviteTask.campaign_id == campaign_id)
            )
            rows = result.all()
            if inspect.isawaitable(rows):
                rows = await rows
            return {int(row[0]) for row in rows}
        except Exception:
            return set()

    async def get_account_daily_count(self, account_id: UUID) -> int:
        """
        Получить количество приглашений аккаунта за сегодня.
        """
        today = datetime.utcnow().date()
        result = await self.session.execute(
            select(func.count(InviteTask.id))
            .where(
                and_(
                    InviteTask.account_id == account_id,
                    InviteTask.invited_at >= today,
                    InviteTask.status == "success",
                )
            )
        )
        return result.scalar() or 0

    async def can_account_invite(
        self, account_id: UUID, campaign: InviteCampaign
    ) -> bool:
        """
        Проверить, может ли аккаунт отправить приглашение сегодня.
        """
        settings = await self._get_effective_settings(campaign)
        daily_limit = await self._get_account_daily_limit(
            Account(id=account_id), settings
        )
        today_count = await self.get_account_daily_count(account_id)
        return today_count < daily_limit

    # ==================== Core Invite Logic ====================

    async def execute_invite_task(self, task_id: UUID) -> dict:
        """
        Основной метод выполнения инвайтинга (будет вызываться из Celery).
        Получает задачу
        Получает аккаунт + прокси
        Берёт клиента из ClientManager
        Выполняет логику инвайта с соблюдением всех настроек безопасности
        """
        # Получаем задачу
        task = await self._get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return {"success": False, "error": "Task not found"}

        # Проверяем, можно ли обработать задачу
        now = datetime.utcnow()
        if task.status == "floodwait" and task.next_attempt_at and task.next_attempt_at > now:
            logger.info(f"Task {task_id} is in floodwait until {task.next_attempt_at}")
            return {"success": False, "error": "Task in floodwait"}

        if task.status not in ["pending", "floodwait"]:
            logger.info(f"Task {task_id} has status {task.status}, skipping")
            return {"success": False, "error": f"Invalid task status: {task.status}"}

        # Обновляем статус на processing
        await self._update_task_status(task_id, "processing")
        logger.bind(task_id=task_id).info("Starting task processing")

        # Получаем кампанию
        campaign = await self.get_campaign(task.campaign_id)
        if not campaign:
            logger.error(f"Campaign {task.campaign_id} not found for task {task_id}")
            await self._update_task_status(
                task_id, "failed", error_code="CAMPAIGN_NOT_FOUND", error_message="Campaign not found"
            )
            await self._create_log(
                task_id, "process_task", False, error_code="CAMPAIGN_NOT_FOUND", error_message="Campaign not found"
            )
            return {"success": False, "error": "Campaign not found"}

        if app_settings.telegram_mock_mode:
            account = await self._get_account(task.account_id)
            if not account:
                await self._update_task_status(
                    task_id,
                    "failed",
                    error_code="ACCOUNT_NOT_FOUND",
                    error_message="Account not found",
                )
                await self._create_log(
                    task_id,
                    "process_task",
                    False,
                    error_code="ACCOUNT_NOT_FOUND",
                    error_message="Account not found",
                )
                return {"success": False, "error": "Account not found"}

            task.status = "success"
            task.attempts = (task.attempts or 0) + 1
            task.invited_at = now
            task.error_code = None
            task.error_message = None
            await self._create_log(task_id, "mock_invite", True)
            try:
                await self._increment_daily_invite_count(task.account_id)
            except Exception:
                logger.debug("Failed to increment mock invite counter", account_id=str(task.account_id))
            await self.session.commit()
            await self.session.refresh(task)
            return {"success": True, "message": "Mock invite succeeded"}

        # Получаем настройки кампании с учётом warmup
        settings = await self._get_effective_settings(campaign)

        # Проверяем, может ли аккаунт отправить приглашение сегодня
        if not await self.can_account_invite(task.account_id, campaign):
            logger.warning(
                f"Account {task.account_id} has reached daily limit for campaign {campaign.id}"
            )
            await self._update_task_status(
                task_id, "failed", error_code="DAILY_LIMIT_EXCEEDED", error_message="Daily limit exceeded"
            )
            await self._create_log(
                task_id,
                "check_limits",
                False,
                error_code="DAILY_LIMIT_EXCEEDED",
                error_message="Daily limit exceeded",
            )
            return {"success": False, "error": "Daily limit exceeded"}

        # Получаем аккаунт и прокси
        account = await self._get_account(task.account_id)
        if not account:
            logger.error(f"Account {task.account_id} not found for task {task_id}")
            await self._update_task_status(
                task_id, "failed", error_code="ACCOUNT_NOT_FOUND", error_message="Account not found"
            )
            await self._create_log(
                task_id, "process_task", False, error_code="ACCOUNT_NOT_FOUND", error_message="Account not found"
            )
            return {"success": False, "error": "Account not found"}

        proxy = None
        if task.proxy_id:
            proxy = await self._get_proxy(task.proxy_id)
            if not proxy:
                logger.warning(
                    f"Proxy {task.proxy_id} not found for task {task_id}, continuing without proxy"
                )

        # Получаем Telegram клиент
        try:
            client = await self.telegram_client_manager.get_client(account, proxy)
        except Exception as e:
            logger.error(f"Failed to get Telegram client for account {account.id}: {e}")
            await self._update_task_status(
                task_id, "failed", error_code="CLIENT_ERROR", error_message=str(e)
            )
            await self._create_log(
                task_id, "get_client", False, error_code="CLIENT_ERROR", error_message=str(e)
            )
            return {"success": False, "error": f"Client error: {e}"}

        try:
            # Проверяем черные списки
            if await self._is_user_blacklisted(
                {"user_id": task.target_user_id, "username": task.target_username}, settings
            ):
                logger.info(
                    f"User {task.target_user_id} is in blacklist for campaign {campaign.id}"
                )
                await self._update_task_status(
                    task_id, "failed", error_code="BLACKLISTED", error_message="User is in blacklist"
                )
                await self._create_log(
                    task_id,
                    "check_blacklist",
                    False,
                    error_code="BLACKLISTED",
                    error_message="User is in blacklist",
                )
                return {"success": False, "error": "User is in blacklist"}

            # Проверяем, не бот ли пользователь
            try:
                user_entity = await client.get_entity(task.target_user_id)
                if getattr(user_entity, "bot", False):
                    logger.info(f"User {task.target_user_id} is a bot")
                    await self._update_task_status(
                        task_id, "failed", error_code="USER_IS_BOT", error_message="User is a bot"
                    )
                    await self._create_log(
                        task_id,
                        "check_user",
                        False,
                        error_code="USER_IS_BOT",
                        error_message="User is a bot",
                    )
                    return {"success": False, "error": "User is a bot"}
            except Exception as e:
                logger.warning(f"Failed to get user entity for {task.target_user_id}: {e}")
                # Если не удалось получить информацию о пользователе, продолжаем проверку

            # Проверяем, является ли пользователь уже участником целевого чата
            try:
                participant = await client.get_participants(
                    campaign.target_chat_id, filter=task.target_user_id
                )
                if participant:
                    logger.info(
                        f"User {task.target_user_id} is already a participant in chat {campaign.target_chat_id}"
                    )
                    await self._update_task_status(
                        task_id,
                        "success",
                        error_code="ALREADY_PARTICIPANT",
                        invited_at=now,
                    )
                    await self._create_log(
                        task_id,
                        "check_user",
                        True,
                        error_code=None,
                        error_message="User is already a participant",
                    )
                    return {"success": True, "message": "User already participant"}
            except Exception as e:
                # Если не удалось проверить, продолжаем, но логируем
                logger.warning(f"Failed to check if user {task.target_user_id} is participant: {e}")

            # Добавляем в контакты, если настроено
            if settings.add_to_contacts_first:
                try:
                    await client.import_contacts([await client.get_entity(task.target_user_id)])
                    logger.info(
                        f"Added user {task.target_user_id} to contacts for account {account.id}"
                    )
                    await self._create_log(task_id, "add_contact", True)
                except Exception as e:
                    logger.warning(f"Failed to add user {task.target_user_id} to contacts: {e}")
                    await self._create_log(
                        task_id,
                        "add_contact",
                        False,
                        error_code=type(e).__name__,
                        error_message=str(e),
                    )
                    # Если не удалось добавить в контакты, но это не критично, продолжаем
                    # Если настройка только добавить в контакты, то считаем задачу неуспешной
                    if settings.only_add_contacts:
                        await self._update_task_status(
                            task_id,
                            "failed",
                            error_code="ADD_CONTACT_FAILED",
                            error_message=str(e),
                        )
                        return {"success": False, "error": f"Add contact failed: {e}"}

            # Если режим только добавить в контакты, то на этом заканчиваем
            if settings.only_add_contacts:
                await self._update_task_status(task_id, "success", invited_at=now)
                logger.info(f"Task {task_id} completed (only add contacts)")
                return {"success": True, "message": "Contact added successfully"}

            # Приглашаем в чат с рандомизацией задержек
            delay = random.uniform(
                settings.invite_delay_min, settings.invite_delay_max
            )
            logger.debug(
                f"Waiting {delay:.2f} seconds before invite for task {task_id}"
            )
            # В реальной реализации здесь должно быть ожидание, но для Celery задачи
            # мы просто логируем задержку, так как реальное ожидание должно быть
            # на уровне планировщика задач

            await client.invite_to_chat(campaign.target_chat_id, [task.target_user_id])
            logger.info(
                f"Invited user {task.target_user_id} to chat {campaign.target_chat_id}"
            )
            await self._update_task_status(task_id, "success", invited_at=now)
            await self._create_log(task_id, "invite_to_chat", True)

            # Обновляем счётчик приглашений за сегодня в Redis для быстрого доступа
            await self._increment_daily_invite_count(task.account_id)

            # Обрабатываем паузу после N успешных инвайтов
            # Считаем успешные инвайты аккаунта за текущую сессию
            success_count = await self._get_account_success_count_in_session(
                task.account_id, settings.pause_after_every
            )
            if success_count >= settings.pause_after_every:
                pause_duration = random.uniform(
                    settings.pause_duration_min, settings.pause_duration_max
                )
                logger.info(
                    f"Account {task.account_id} taking pause for {pause_duration:.2f} minutes after {settings.pause_after_every} invites"
                )
                # В реальной реализации здесь должно быть ожидание паузы
                # Но мы просто логируем, так как реальное ожидание должно быть
                # на уровне планировщика задач

            return {"success": True, "message": "Invite sent successfully"}

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError for task {task_id}: {e.seconds} seconds")
            next_attempt = now + timedelta(seconds=e.seconds)
            await self._update_task_status(
                task_id,
                "floodwait",
                error_code="FLOOD_WAIT",
                error_message=str(e),
                next_attempt_at=next_attempt,
            )
            await self._create_log(
                task_id, "invite_to_chat", False, error_code="FLOOD_WAIT", error_message=str(e)
            )
            return {
                "success": False,
                "error": f"Flood wait: {e.seconds} seconds",
                "retry_after": e.seconds,
            }

        except UserAlreadyParticipantError:
            logger.info(
                f"User {task.target_user_id} is already a participant in chat {campaign.target_chat_id}"
            )
            await self._update_task_status(
                task_id,
                "success",
                error_code="ALREADY_PARTICIPANT",
                invited_at=now,
            )
            await self._create_log(task_id, "invite_to_chat", True)
            return {"success": True, "message": "User already participant"}

        except UserNotMutualContactError:
            logger.warning(f"User {task.target_user_id} is not a mutual contact")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="NOT_MUTUAL_CONTACT",
                error_message="User is not a mutual contact",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="NOT_MUTUAL_CONTACT",
                error_message="User is not a mutual contact",
            )
            return {"success": False, "error": "User is not a mutual contact"}

        except UserPrivacyRestrictedError:
            logger.warning(
                f"User {task.target_user_id} has privacy settings restricting invites"
            )
            await self._update_task_status(
                task_id,
                "failed",
                error_code="PRIVACY_RESTRICTED",
                error_message="User privacy settings restrict invites",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="PRIVACY_RESTRICTED",
                error_message="User privacy settings restrict invites",
            )
            return {"success": False, "error": "User privacy settings restrict invites"}

        except PeerFloodError:
            logger.warning(f"PeerFloodError for account {account.id}")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="PEER_FLOOD",
                error_message="Too many invites, account is limited",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="PEER_FLOOD",
                error_message="Too many invites, account is limited",
            )
            # Помечаем аккаунт как нуждающийся в охлаждении на длительный срок
            # В реальной реализации здесь можно обновить статус аккаунта
            return {"success": False, "error": "Peer flood error"}

        except ChatAdminRequiredError:
            logger.error(f"Chat admin required for chat {campaign.target_chat_id}")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="CHAT_ADMIN_REQUIRED",
                error_message="Bot is not admin in the target chat",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="CHAT_ADMIN_REQUIRED",
                error_message="Bot is not admin in the target chat",
            )
            return {"success": False, "error": "Chat admin required"}

        except ChannelPrivateError:
            logger.error(f"Channel {campaign.target_chat_id} is private")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="CHANNEL_PRIVATE",
                error_message="Target chat is private",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="CHANNEL_PRIVATE",
                error_message="Target chat is private",
            )
            return {"success": False, "error": "Channel private"}

        except UserBannedInChannelError:
            logger.info(f"User {task.target_user_id} is banned in channel {campaign.target_chat_id}")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="USER_BANNED",
                error_message="User is banned in the target chat",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="USER_BANNED",
                error_message="User is banned in the target chat",
            )
            return {"success": False, "error": "User banned in channel"}

        except InviteRequestSentError:
            logger.info(f"Invite request sent for user {task.target_user_id} (requires approval)")
            await self._update_task_status(
                task_id,
                "success",
                error_code="INVITE_REQUEST_SENT",
                invited_at=now,
            )
            await self._create_log(task_id, "invite_to_chat", True)
            return {"success": True, "message": "Invite request sent"}

        except UserIsBlockedError:
            logger.warning(f"User {task.target_user_id} has blocked the account")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="USER_BLOCKED",
                error_message="User has blocked the account",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="USER_BLOCKED",
                error_message="User has blocked the account",
            )
            return {"success": False, "error": "User blocked the account"}

        except ChatWriteForbiddenError:
            logger.warning(f"Cannot write to chat {campaign.target_chat_id}")
            await self._update_task_status(
                task_id,
                "failed",
                error_code="CHAT_WRITE_FORBIDDEN",
                error_message="Cannot write to target chat",
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="CHAT_WRITE_FORBIDDEN",
                error_message="Cannot write to target chat",
            )
            return {"success": False, "error": "Cannot write to chat"}

        except Exception as e:
            logger.error(f"Unexpected error inviting user {task.target_user_id}: {e}", exc_info=True)
            await self._update_task_status(
                task_id, "failed", error_code="UNKNOWN_ERROR", error_message=str(e)
            )
            await self._create_log(
                task_id,
                "invite_to_chat",
                False,
                error_code="UNKNOWN_ERROR",
                error_message=str(e),
            )
            return {"success": False, "error": f"Unexpected error: {e}"}

        finally:
            # Освобождаем клиент
            await self.telegram_client_manager.release_client(client)

    # ==================== Helper Methods ====================

    async def _get_effective_settings(self, campaign: InviteCampaign) -> InviteSettings:
        """
        Получить эффективные настройки кампании с учётом warmup и других факторов.
        """
        settings = InviteSettings(
            daily_limit_per_account=campaign.daily_limit_per_account,
            invite_delay_min=campaign.invite_delay_min,
            invite_delay_max=campaign.invite_delay_max,
            pause_after_every=campaign.pause_after_every,
            pause_duration_min=campaign.pause_duration_min,
            pause_duration_max=campaign.pause_duration_max,
            warmup_enabled=campaign.warmup_enabled,
            warmup_days=campaign.warmup_days,
            warmup_limit_factor=campaign.warmup_limit_factor,
            only_add_contacts=campaign.only_add_contacts,
            add_to_contacts_first=campaign.add_to_contacts_first,
            blacklist_usernames=(
                campaign.blacklist_usernames.split(",")
                if campaign.blacklist_usernames
                else []
            ),
            blacklist_user_ids=(
                [int(x) for x in campaign.blacklist_user_ids.split(",")]
                if campaign.blacklist_user_ids
                else []
            ),
        )
        return settings

    async def _get_account_daily_limit(
        self, account: Account, settings: InviteSettings
    ) -> int:
        """
        Вычислить текущий дневной лимит аккаунта с учётом warmup.
        """
        daily_limit = settings.daily_limit_per_account
        if settings.warmup_enabled and account.created_at:
            # Вычисляем дни с момента создания аккаунта
            account_age_days = (datetime.utcnow() - account.created_at).days
            if account_age_days < settings.warmup_days:
                daily_limit = int(daily_limit * settings.warmup_limit_factor)
        return max(1, daily_limit)  # Минимум 1

    async def _is_user_blacklisted(self, user: dict, settings: InviteSettings) -> bool:
        """
        Проверить, находится ли пользователь в черных списках.
        """
        if settings.blacklist_usernames and user.get("username"):
            if user["username"] in settings.blacklist_usernames:
                return True
        if settings.blacklist_user_ids and user.get("user_id"):
            if user["user_id"] in settings.blacklist_user_ids:
                return True
        return False

    async def _get_available_accounts(
        self, campaign: InviteCampaign, settings: InviteSettings
    ) -> List[Account]:
        """
        Получить список доступных аккаунтов для кампании.
        В реальной реализации нужно фильтровать по статусу, прогреву и т.д.
        """
        result = await self.session.execute(
            select(Account).where(Account.is_active == True)
        )
        accounts = result.scalars().all()

        # Фильтруем аккаунты по дневному лимиту
        available_accounts = []
        for account in accounts:
            daily_limit = await self._get_account_daily_limit(account, settings)
            today_count = await self.get_account_daily_count(account.id)
            if today_count < daily_limit:
                available_accounts.append(account)

        return available_accounts

    async def _get_target_users(self, campaign: InviteCampaign) -> List[dict]:
        """
        Получить список пользователей для приглашения из источника.
        Поддерживает:
          - parsed_list: загрузка из ParsedUser по source_parsed_chat_id
          - chat: получение участников из source_chat_id (через Telethon)
          - uploaded_list: получение из загруженного списка (пока заглушка)
        """
        # Режим parsed_list — берём из ParsedUser
        if campaign.source_type == "parsed_list" and campaign.source_parsed_chat_id:
            result = await self.session.execute(
                select(ParsedUser).where(
                    ParsedUser.chat_id == campaign.source_parsed_chat_id
                )
            )
            parsed_users = result.scalars().all()
            target_users = []
            for pu in parsed_users:
                # Пропускаем ботов, скам, фейки
                if pu.is_bot or pu.is_scam or pu.is_fake:
                    continue
                target_users.append({
                    "user_id": pu.user_id,
                    "username": pu.username,
                })
            return target_users

        # Режим chat — получаем через Telethon
        if campaign.source_type == "chat" and campaign.source_chat_id:
            # Здесь в реальной реализации получение участников через Telethon
            logger.warning(
                f"Telethon source_chat lookup not implemented yet, "
                f"source_chat_id={campaign.source_chat_id}"
            )
            pass

        # Режим uploaded_list
        if campaign.source_type == "uploaded_list":
            logger.warning("uploaded_list source not implemented yet")
            pass

        # Если ничего не нашли — пустой список
        return []

    async def _get_task(self, task_id: UUID) -> Optional[InviteTask]:
        """Получить задачу по ID."""
        result = await self.session.execute(
            select(InviteTask).where(InviteTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def _get_account(self, account_id: UUID) -> Optional[Account]:
        """Получить аккаунт по ID."""
        result = await self.session.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def _get_proxy(self, proxy_id: UUID) -> Optional[Proxy]:
        """Получить прокси по ID."""
        result = await self.session.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        return result.scalar_one_or_none()

    async def _create_task(self, task_data: InviteTaskCreate) -> InviteTask:
        """Создать новую задачу."""
        task = InviteTask(**task_data.model_dump())
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def _update_task_status(
        self,
        task_id: UUID,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        invited_at: Optional[datetime] = None,
        next_attempt_at: Optional[datetime] = None,
    ) -> Optional[InviteTask]:
        """Обновить статус задачи."""
        task = await self._get_task(task_id)
        if not task:
            return None

        task.status = status
        if error_code is not None:
            task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message
        if invited_at is not None:
            task.invited_at = invited_at
        if next_attempt_at is not None:
            task.next_attempt_at = next_attempt_at
        if status in ["success", "failed", "floodwait"]:
            task.attempts += 1
            if status == "success":
                task.next_attempt_at = None
            elif status == "floodwait" and next_attempt_at is None:
                # Для floodwait устанавливаем время следующей попытки на 5 минут по умолчанию
                task.next_attempt_at = datetime.utcnow() + timedelta(minutes=5)

        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def _create_log(
        self,
        task_id: UUID,
        action: str,
        success: bool,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> InviteLog:
        """Создать запись лога."""
        log = InviteLog(
            invite_task_id=task_id,
            action=action,
            success=success,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def _increment_daily_invite_count(self, account_id: UUID) -> None:
        """Увеличить счётчик ежедневных приглашений в Redis."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"daily_invites:{account_id}:{today}"
        await self.redis.incr(key)
        # Устанавливаем время жизни ключа на 24 часа
        await self.redis.expire(key, 86400)

    async def _get_account_success_count_in_session(
        self, account_id: UUID, pause_after_every: int
    ) -> int:
        """
        Получить количество успешных приглашений аккаунта в текущей сессии.
        В реальной реализации это должно храниться в памяти или Redis с коротким TTL.
        Для простоты возвращаем 0, так как точная реализация зависит от архитектуры Celery workers.
        """
        # Это упрощённая реализация. В продакшене нужно использовать Redis или другую
        # систему для хранения счётчиков между задачами Celery
        key = f"session_invites:{account_id}"
        count = await self.redis.get(key)
        return int(count) if count else 0
