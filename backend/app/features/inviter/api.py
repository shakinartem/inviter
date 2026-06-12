from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.auth.models import User
from app.features.inviter.schemas import (
    InviteCampaignCreate,
    InviteCampaignUpdate,
    InviteCampaignResponse,
    InviteCampaignList,
    InviteTaskCreate,
    InviteTaskResponse,
    InviteLogResponse,
    CampaignStats,
    StartCampaignRequest,
    InviteCampaignFilter,
)
from app.features.inviter.service import InviterService
from app.features.inviter.tasks import run_campaign as run_campaign_task
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/campaigns",
    tags=["Inviter"],
)


async def get_inviter_service(session: AsyncSession = Depends(get_db_session)) -> InviterService:
    """
    Dependency to get InviterService instance.
    """
    from app.features.telegram.client_manager import TelegramClientManager
    from app.db.redis import get_redis

    redis = await get_redis()
    telegram_client_manager = TelegramClientManager()
    return InviterService(session, telegram_client_manager, redis)


@router.post("/", response_model=InviteCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_in: InviteCampaignCreate,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Создать новую кампанию инвайтинга.
    """
    logger.bind(user_id=current_user.id).info("Creating campaign")
    campaign = await service.create_campaign(campaign_in, current_user.id)
    logger.bind(user_id=current_user.id, campaign_id=campaign.id).info("Campaign created")
    return campaign


@router.get("/", response_model=List[InviteCampaignList])
async def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    filters: InviteCampaignFilter = Depends(),
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Получить список кампаний текущего пользователя с фильтрацией и пагинацией.
    """
    logger.bind(user_id=current_user.id).info("Listing campaigns")
    campaigns = await service.get_campaigns(
        owner_id=current_user.id,
        filters=filters.model_dump(exclude_unset=True),
        skip=skip,
        limit=limit,
    )
    return campaigns


@router.get("/{campaign_id}", response_model=InviteCampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Получить кампанию по ID.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Getting campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой кампании",
        )
    return campaign


@router.patch("/{campaign_id}", response_model=InviteCampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    campaign_in: InviteCampaignUpdate,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Обновить существующую кампанию.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Updating campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для обновления этой кампании",
        )
    updated_campaign = await service.update_campaign(campaign_id, campaign_in)
    if not updated_campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign updated")
    return updated_campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Удалить кампанию по ID.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Deleting campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления этой кампании",
        )
    success = await service.delete_campaign(campaign_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign deleted")
    return None


@router.post("/{campaign_id}/start", response_model=dict)
async def start_campaign(
    campaign_id: UUID,
    start_request: Optional[StartCampaignRequest] = None,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Запустить кампанию инвайтинга.
    Проверяет права владельца и запускает Celery задачу для обработки кампании.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Starting campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для запуска этой кампании",
        )
    if campaign.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Кампания должна быть в статусе черновика для запуска. Текущий статус: {campaign.status}",
        )

    # Запускаем Celery задачу для обработки кампании
    task = run_campaign_task.delay(campaign_id, current_user.id)
    logger.bind(
        user_id=current_user.id,
        campaign_id=campaign_id,
        celery_task_id=task.id,
    ).info("Campaign start task dispatched")

    return {
        "success": True,
        "message": "Кампания запущена в фоновом режиме",
        "task_id": task.id,
    }


@router.post("/{campaign_id}/pause", response_model=dict)
async def pause_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Поставить кампанию на паузу.
    Проверяет права владельца.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Pausing campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для паузы этой кампании",
        )
    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Кампания должна быть активной для паузы. Текущий статус: {campaign.status}",
        )

    success = await service.pause_campaign(campaign_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось поставить кампанию на паузу",
        )
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign paused")
    return {"success": True, "message": "Кампания поставлена на паузу"}


@router.post("/{campaign_id}/stop", response_model=dict)
async def stop_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Остановить кампанию.
    Проверяет права владельца.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Stopping campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для остановки этой кампании",
        )
    if campaign.status not in ["active", "paused"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Кампания должна быть активной или на паузе для остановки. Текущий статус: {campaign.status}",
        )

    success = await service.stop_campaign(campaign_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось остановить кампанию",
        )
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign stopped")
    return {"success": True, "message": "Кампания остановлена"}


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Получить статистику кампании.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Getting campaign stats")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к статистике этой кампании",
        )
    stats = await service.get_campaign_stats(campaign_id)
    return stats


@router.get("/{campaign_id}/tasks", response_model=List[InviteTaskResponse])
async def get_campaign_tasks(
    campaign_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Получить список задач кампании с фильтрацией по статусу и пагинацией.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Getting campaign tasks")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к задачам этой кампании",
        )
    tasks = await service.get_campaign_tasks(
        campaign_id=campaign_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return tasks


@router.get("/{campaign_id}/logs", response_model=List[InviteLogResponse])
async def get_campaign_logs(
    campaign_id: UUID,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Получить список логов кампании с пагинацией.
    Проверяет, что кампания принадлежит текущему пользователю.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Getting campaign logs")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к логам этой кампании",
        )
    # Получаем все задачи кампании, чтобы получить их ID для фильтрации логов
    # Но для простоты мы можем получить логи через сервис, если у него есть такой метод
    # В текущей реализации сервиса нет метода для получения логов по кампании напрямую
    # Поэтому мы получим все задачи кампании, затем получим логи для каждой задачи
    # Это может быть неэффективно для больших кампаний, но для демонстрации подойдет
    # В реальной реализации лучше добавить метод в сервис для получения логов по campaign_id
    tasks = await service.get_campaign_tasks(campaign_id=campaign_id, skip=0, limit=1000)  # Получим все задачи
    task_ids = [task.id for task in tasks]
    logs = []
    for task_id in task_ids:
        task_logs = await service.get_task_logs(task_id, limit=100)  # Ограничиваем на задачу
        logs.extend(task_logs)
    # Сортируем по дате создания в обратном порядке и применяем пагинацию
    logs.sort(key=lambda x: x.created_at, reverse=True)
    paginated_logs = logs[skip:skip+limit]
    return paginated_logs


@router.post("/bulk-create-tasks", response_model=dict)
async def bulk_create_tasks(
    task_in: InviteTaskCreate,
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """
    Создать множество задач для кампании (для загрузки своего списка пользователей).
    В реальной реализации здесь должна быть логика принятия списка пользователей и создания задач для каждого.
    Для демонстрации создаем одну задачу.
    """
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Bulk creating tasks")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кампания не найдена",
        )
    if campaign.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для создания задач в этой кампании",
        )
    # В реальной реализации здесь должен быть цикл по списку пользователей
    # Для демонстрации создаем одну задачу
    task = await service.create_task(task_in)
    logger.bind(user_id=current_user.id, campaign_id=campaign_id, task_id=task.id).info("Task created")
    return {
        "success": True,
        "message": "Задача создана",
        "task_id": task.id,
    }