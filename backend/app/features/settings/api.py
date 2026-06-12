from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_superuser
from app.db.session import get_db_session
from app.features.auth.models import User
from app.features.settings.schemas import (
    LogoUploadResponse,
    SettingsRead,
    SettingsUpdate,
)
from app.features.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> SettingsService:
    return SettingsService(session=session)


@router.get("/", response_model=SettingsRead)
async def get_settings(
    current_user: User = Depends(get_current_active_user),
    service: SettingsService = Depends(get_service),
):
    """Get current site settings (singleton)."""
    settings = await service.get_settings()
    return settings


@router.put("/", response_model=SettingsRead)
async def update_settings(
    payload: SettingsUpdate,
    current_user: User = Depends(get_current_superuser),
    service: SettingsService = Depends(get_service),
):
    """Update site settings."""
    settings = await service.update_settings(payload)
    return settings


@router.post("/logo", response_model=LogoUploadResponse)
async def upload_logo(
    file: UploadFile = File(..., description="Logo image (png/jpg/jpeg/webp)"),
    current_user: User = Depends(get_current_superuser),
    service: SettingsService = Depends(get_service),
):
    """Upload and set the site logo."""
    logo_path = await service.upload_logo(file)
    return LogoUploadResponse(
        logo_path=logo_path,
        message="Logo uploaded successfully",
    )


@router.delete("/logo", response_model=LogoUploadResponse)
async def delete_logo(
    current_user: User = Depends(get_current_superuser),
    service: SettingsService = Depends(get_service),
):
    """Remove the site logo."""
    await service.delete_logo()
    return LogoUploadResponse(
        logo_path=None,
        message="Logo removed successfully",
    )
