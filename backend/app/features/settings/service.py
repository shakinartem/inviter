from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settings.models import SINGLETON_ID, SiteSettings
from app.features.settings.schemas import SettingsUpdate


BASE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR = BASE_UPLOAD_DIR / "logo"
MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_LOGO_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _get_or_create_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def _cleanup_logo_dir(except_filename: str | None = None) -> None:
    if not UPLOAD_DIR.exists():
        return
    for path in UPLOAD_DIR.glob("logo.*"):
        if except_filename and path.name == except_filename:
            continue
        if path.is_file():
            path.unlink(missing_ok=True)


def _validate_logo_upload(file: UploadFile) -> str:
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported logo format. Allowed: png, jpg, jpeg, webp",
        )

    content_type = (file.content_type or "").lower()
    expected_content_type = ALLOWED_LOGO_EXTENSIONS[ext]
    if content_type != expected_content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid logo content type. Expected {expected_content_type}",
        )

    return ext


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_settings(self) -> SiteSettings:
        """Get the sole settings row, or create one with defaults."""
        result = await self.session.execute(
            select(SiteSettings).where(SiteSettings.id == SINGLETON_ID)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = SiteSettings(
                id=SINGLETON_ID,
                language="ru",
                site_name="Inviter Pro",
                logo_path=None,
                help_text=None,
                system_config=None,
            )
            self.session.add(settings)
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                result = await self.session.execute(
                    select(SiteSettings).where(SiteSettings.id == SINGLETON_ID)
                )
                settings = result.scalar_one()
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
        file_ext = _validate_logo_upload(file)
        filename = f"logo{file_ext}"
        file_path = upload_dir / filename
        contents = await file.read(MAX_LOGO_SIZE_BYTES + 1)
        if len(contents) > MAX_LOGO_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Logo is too large. Maximum size is 5 MB",
            )

        _cleanup_logo_dir(except_filename=filename)
        file_path.write_bytes(contents)
        settings = await self.get_settings()
        relative_path = f"uploads/logo/{filename}"
        settings.logo_path = relative_path
        await self.session.commit()
        logger.info(f"Logo uploaded to {relative_path}")
        return relative_path

    async def delete_logo(self) -> None:
        settings = await self.get_settings()
        logo_path = settings.logo_path
        settings.logo_path = None
        await self.session.commit()

        if logo_path:
            relative_path = Path(logo_path)
            try:
                file_path = BASE_UPLOAD_DIR / relative_path.relative_to("uploads")
            except ValueError:
                file_path = UPLOAD_DIR / relative_path.name
            if file_path.exists():
                file_path.unlink()
        _cleanup_logo_dir()
