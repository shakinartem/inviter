from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

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
    InviteCampaignFilter,
)
from app.features.inviter.service import InviterService

router = APIRouter(
    prefix="/campaigns",
    tags=["Inviter"],
)


async def get_inviter_service(session: AsyncSession = Depends(get_db_session)) -> InviterService:
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
    logger.bind(user_id=current_user.id).info("Listing campaigns")
    return await service.get_campaigns(
        owner_id=current_user.id,
        filters=filters.model_dump(exclude_unset=True),
        skip=skip,
        limit=limit,
    )


@router.get("/{campaign_id}", response_model=InviteCampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для доступа к этой кампании")
    return campaign


@router.patch("/{campaign_id}", response_model=InviteCampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    campaign_in: InviteCampaignUpdate,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для обновления этой кампании")
    updated_campaign = await service.update_campaign(campaign_id, campaign_in)
    if not updated_campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign updated")
    return updated_campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для удаления этой кампании")
    if not await service.delete_campaign(campaign_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign deleted")
    return None


@router.post("/{campaign_id}/start", response_model=dict, deprecated=True)
async def start_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    """Legacy launch route retained only to return an explicit migration signal."""
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для запуска этой кампании")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "PREFLIGHT_REQUIRED",
            "message": "Legacy campaign Start is disabled. Launch through fresh Execution Preflight.",
            "launch_endpoint": f"/orchestration/campaigns/{campaign_id}/preflight/start",
        },
    )


@router.post("/{campaign_id}/pause", response_model=dict)
async def pause_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Pausing campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для паузы этой кампании")
    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Кампания должна быть активной для паузы. Текущий статус: {campaign.status}",
        )
    if not await service.pause_campaign(campaign_id):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось поставить кампанию на паузу")
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign paused")
    return {"success": True, "message": "Кампания поставлена на паузу"}


@router.post("/{campaign_id}/stop", response_model=dict)
async def stop_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Stopping campaign")
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для остановки этой кампании")
    if campaign.status not in ["active", "paused"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Кампания должна быть активной или на паузе для остановки. Текущий статус: {campaign.status}",
        )
    if not await service.stop_campaign(campaign_id):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось остановить кампанию")
    logger.bind(user_id=current_user.id, campaign_id=campaign_id).info("Campaign stopped")
    return {"success": True, "message": "Кампания остановлена"}


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для доступа к статистике этой кампании")
    return await service.get_campaign_stats(campaign_id)


@router.get("/{campaign_id}/tasks", response_model=List[InviteTaskResponse])
async def get_campaign_tasks(
    campaign_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для доступа к задачам этой кампании")
    return await service.get_campaign_tasks(
        campaign_id=campaign_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/{campaign_id}/logs", response_model=List[InviteLogResponse])
async def get_campaign_logs(
    campaign_id: UUID,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для доступа к логам этой кампании")
    tasks = await service.get_campaign_tasks(campaign_id=campaign_id, skip=0, limit=1000)
    logs = []
    for task in tasks:
        logs.extend(await service.get_task_logs(task.id, limit=100))
    logs.sort(key=lambda item: item.created_at, reverse=True)
    return logs[skip:skip + limit]


@router.post("/bulk-create-tasks", response_model=dict)
async def bulk_create_tasks(
    task_in: InviteTaskCreate,
    campaign_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: InviterService = Depends(get_inviter_service),
):
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кампания не найдена")
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для создания задач в этой кампании")
    task = await service.create_task(task_in)
    logger.bind(user_id=current_user.id, campaign_id=campaign_id, task_id=task.id).info("Task created")
    return {
        "success": True,
        "message": "Задача создана",
        "task_id": task.id,
    }
