from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from loguru import logger
from celery import Celery
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.features.inviter.service import InviterService
from app.features.inviter.models import InviteCampaign, InviteTask
from app.features.telegram.client_manager import TelegramClientManager
from app.core.config import settings
from app.db.redis import get_redis


# Инициализация зависимостей для задач
async def get_inviter_service() -> InviterService:
    """Создать экземпляр InviterService с необходимыми зависимостями."""
    async with AsyncSessionLocal() as session:
        redis = await get_redis()
        telegram_client_manager = TelegramClientManager()
        return InviterService(session, telegram_client_manager, redis)


@celery_app.task(name="inviter.run_campaign", bind=True, max_retries=3)
async def run_campaign(self, campaign_id: UUID, user_id: UUID) -> dict:
    """
    Запуск всей кампании в фоне.
    Отвечает за подготовку задач и запуск их выполнения.
    """
    logger.bind(campaign_id=campaign_id, user_id=user_id).info("Starting campaign")
    
    try:
        # Создаем сервис
        inviter_service = await get_inviter_service()
        
        # Запускаем кампанию через сервис
        result = await inviter_service.start_campaign(campaign_id, user_id)
        
        if not result["success"]:
            logger.bind(campaign_id=campaign_id).error(
                f"Failed to start campaign: {result['message']}"
            )
            return result
            
        logger.bind(campaign_id=campaign_id).info(
            f"Campaign started successfully: {result['message']}"
        )
        return result
        
    except Exception as e:
        logger.bind(campaign_id=campaign_id, user_id=user_id).error(
            f"Error in run_campaign task: {e}", exc_info=True
        )
        # Повторяем задачу при ошибке
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="inviter.execute_single_invite", bind=True, max_retries=5)
async def execute_single_invite(self, task_id: UUID) -> dict:
    """
    Выполнение одной InviteTask.
    Основная задача, которая вызывает inviter_service.execute_invite_task(task_id).
    """
    logger.bind(task_id=task_id).info("Executing single invite task")
    
    try:
        # Создаем сервис
        inviter_service = await get_inviter_service()
        
        # Выполняем задачу
        result = await inviter_service.execute_invite_task(task_id)
        
        # Обрабатываем результат
        if result.get("success"):
            logger.bind(task_id=task_id).info("Task executed successfully")
            
            # После успешного выполнения проверяем, нужно ли запускать следующую задачу
            # Это делается через проверку активных задач в кампании
            async with AsyncSessionLocal() as session:
                # Получаем задачу чтобы получить campaign_id
                from app.features.inviter.models import InviteTask
                task_result = await session.execute(
                    select(InviteTask).where(InviteTask.id == task_id)
                )
                task = task_result.scalar_one_or_none()
                
                if task:
                    # Проверяем, есть ли еще pending задачи в кампании
                    pending_count_result = await session.execute(
                        select(func.count(InviteTask.id))
                        .where(
                            and_(
                                InviteTask.campaign_id == task.campaign_id,
                                InviteTask.status == "pending"
                            )
                        )
                    )
                    pending_count = pending_count_result.scalar()
                    
                    if pending_count > 0:
                        logger.bind(
                            task_id=task_id, 
                            campaign_id=task.campaign_id
                        ).info(
                            f"There are {pending_count} pending tasks remaining in campaign"
                        )
                        # В реальной реализации здесь можно запустить следующую задачу
                        # Но мы полагаемся на Celery beat или внешний планировщик
                        
        else:
            # Обрабатываем ошибки
            error = result.get("error", "Unknown error")
            logger.bind(task_id=task_id).warning(
                f"Task execution failed: {error}"
            )
            
            # Повторяем при определенных типах ошибок
            retry_errors = [
                "FLOOD_WAIT",
                "PEER_FLOOD", 
                "CLIENT_ERROR",
                "UNKNOWN_ERROR"
            ]
            
            if any(err in error for err in retry_errors):
                logger.bind(task_id=task_id).info(
                    f"Retrying task due to error: {error}"
                )
                # Используем экспоненциальную задержку для retry
                countdown = min(60 * (2 ** self.request.retries), 300)  # Макс 5 минут
                raise self.retry(exc=Exception(error), countdown=countdown)
            else:
                logger.bind(task_id=task_id).info(
                    f"Not retrying task due to non-retryable error: {error}"
                )
                
        return result
        
    except Exception as e:
        logger.bind(task_id=task_id).error(
            f"Error in execute_single_invite task: {e}", exc_info=True
        )
        # Повторяем задачу при критических ошибках
        raise self.retry(exc=e, countdown=60, max_retries=5)


@celery_app.task(name="inviter.retry_floodwait_tasks")
async def retry_floodwait_tasks() -> dict:
    """
    Периодическая задача для повторного запуска задач после FloodWait.
    Находит все задачи со статусом floodwait, у которых время ожидания истекло,
    и переводит их в статус pending для повторного выполнения.
    """
    logger.info("Starting floodwait retry task")
    
    try:
        async with AsyncSessionLocal() as session:
            now = datetime.utcnow()
            
            # Находим задачи со статусом floodwait, у которых время вышло
            result = await session.execute(
                select(InviteTask)
                .where(
                    and_(
                        InviteTask.status == "floodwait",
                        InviteTask.next_attempt_at <= now
                    )
                )
            )
            floodwait_tasks = result.scalars().all()
            
            if not floodwait_tasks:
                logger.info("No floodwait tasks ready for retry")
                return {"success": True, "retried_count": 0}
                
            # Переводим задачи в статус pending
            retried_count = 0
            for task in floodwait_tasks:
                task.status = "pending"
                task.next_attempt_at = None
                retried_count += 1
                
            await session.commit()
            
            logger.info(
                f"Reset {retried_count} floodwait tasks to pending status"
            )
            
            # Запускаем выполнение этих задач
            for task in floodwait_tasks:
                # Запускаем задачу выполнения приглашения
                execute_single_invite.delay(task.id)
                
            return {
                "success": True, 
                "retried_count": retried_count,
                "message": f"Reset {retried_count} floodwait tasks for retry"
            }
            
    except Exception as e:
        logger.error(f"Error in retry_floodwait_tasks: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@celery_app.task(name="inviter.monitor_campaigns")
async def monitor_campaigns() -> dict:
    """
    Мониторинг активных кампаний.
    Проверяет статус кампаний и обновляет их при необходимости.
    """
    logger.info("Starting campaign monitoring task")
    
    try:
        async with AsyncSessionLocal() as session:
            # Находим активные кампании, которые могут быть завершены
            result = await session.execute(
                select(InviteCampaign)
                .where(InviteCampaign.status == "active")
            )
            active_campaigns = result.scalars().all()
            
            completed_count = 0
            
            for campaign in active_campaigns:
                # Проверяем, все ли задачи кампании завершены
                from app.features.inviter.models import InviteTask
                
                total_result = await session.execute(
                    select(func.count(InviteTask.id))
                    .where(InviteTask.campaign_id == campaign.id)
                )
                total_tasks = total_result.scalar()
                
                completed_result = await session.execute(
                    select(func.count(InviteTask.id))
                    .where(
                        and_(
                            InviteTask.campaign_id == campaign.id,
                            InviteTask.status == "success"
                        )
                    )
                )
                completed_tasks = completed_result.scalar()
                
                # Если все задачи успешные или нет задач вообще, завершаем кампанию
                if total_tasks > 0 and completed_tasks == total_tasks:
                    campaign.status = "completed"
                    campaign.finished_at = datetime.utcnow()
                    completed_count += 1
                    logger.info(
                        f"Campaign {campaign.id} completed automatically "
                        f"({completed_tasks}/{total_tasks} tasks successful)"
                    )
                    
            if completed_count > 0:
                await session.commit()
                logger.info(f"Automatically completed {completed_count} campaigns")
                
            return {
                "success": True,
                "monitored_campaigns": len(active_campaigns),
                "completed_campaigns": completed_count
            }
            
    except Exception as e:
        logger.error(f"Error in monitor_campaigns: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# Настройка периодических задач через Celery Beat
# Это должно быть добавлено в конфигурацию Celery Beat
# Например, в app/tasks/celery_app.py или в отдельном конфигурационном файле
def setup_periodic_tasks(sender: Celery, **kwargs):
    """Настройка периодических задач для модуля инвайтинга."""
    # Задача для повторного запуска floodwait задач каждые 30 секунд
    sender.add_periodic_task(
        30.0,
        retry_floodwait_tasks.s(),
        name="inviter retry floodwait tasks every 30 seconds"
    )
    
    # Задача для мониторинга кампаний каждые 5 минут
    sender.add_periodic_task(
        300.0,
        monitor_campaigns.s(),
        name="inviter monitor campaigns every 5 minutes"
    )


# Подключаем обработчик настройки периодических задач
celery_app.on_after_finalize.connect(setup_periodic_tasks)