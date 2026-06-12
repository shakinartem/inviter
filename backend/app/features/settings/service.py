from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settings.models import SiteSettings
from app.features.settings.schemas import SettingsUpdate


UPLOAD_DIR = Path("uploads/logo")


def _get_or_create_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_settings(self) -> SiteSettings:
        """Get the sole settings row, or create one with defaults."""
        result = await self.session.execute(select(SiteSettings).limit(1))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = SiteSettings(
                id=uuid.uuid4(),
                language="ru",
                site_name="Inviter Pro",
                logo_path=None,
                help_text=None,
                system_config=None,
            )
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        return settings

    async def update_settings(self, payload: SettingsUpdate) -> SiteSettings:
        settings = await self.get_settings()
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def upload_logo(self, file: UploadFile) -> str:
        upload_dir = _get_or_create_upload_dir()
        file_ext = Path(file.filename or "logo.png").suffix or ".png"
        filename = f"logo{file_ext}"
        file_path = upload_dir / filename
        contents = await file.read()
        file_path.write_bytes(contents)
        settings = await self.get_settings()
        relative_path = f"uploads/logo/{filename}"
        settings.logo_path = relative_path
        await self.session.commit()
        logger.info(f"Logo uploaded to {relative_path}")
        return relative_path