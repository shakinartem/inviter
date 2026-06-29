"""
API endpoints для управления платформами.

Эндпоинты (только для чтения):
- GET /platforms — список всех платформ с возможностями
- GET /platforms/{platform} — информация о конкретной платформе
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_active_user
from app.features.auth.models import User
from app.features.platform.models import get_all_platforms, get_platform_capabilities
from app.features.platform.adapter import get_adapter_for_platform

router = APIRouter(prefix="/platforms", tags=["Platforms"])


@router.get(
    "/",
    summary="Список платформ",
    description="Получить список всех платформ с их возможностями и статусом.",
)
async def list_platforms(
    current_user: User = Depends(get_current_active_user),
):
    """Список платформ (для авторизованных пользователей)."""
    return {
        "platforms": get_all_platforms(),
        "total": len(get_all_platforms()),
    }


@router.get(
    "/{platform}",
    summary="Информация о платформе",
    description="Получить детальную информацию о платформе, включая адаптер.",
)
async def get_platform(
    platform: str,
    current_user: User = Depends(get_current_active_user),
):
    """Информация о конкретной платформе."""
    capabilities = get_platform_capabilities(platform)
    if not capabilities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform '{platform}' not found",
        )

    adapter = get_adapter_for_platform(platform)
    adapter_info = adapter.list_capabilities() if adapter else None

    return {
        "platform": capabilities,
        "adapter": adapter_info,
    }