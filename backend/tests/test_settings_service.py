from __future__ import annotations

from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.features.settings.models import SINGLETON_ID, SiteSettings
from app.features.settings.service import SettingsService
import app.features.settings.service as settings_service


class FakeUploadFile:
    def __init__(self, filename: str, content_type: str, data: bytes) -> None:
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._data
        return self._data[:size]


class SettingsServiceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.base_upload_dir = Path.cwd() / "uploads"
        self.logo_dir = self.base_upload_dir / "logo"

        self.base_upload_dir_patch = patch.object(settings_service, "BASE_UPLOAD_DIR", self.base_upload_dir)
        self.upload_dir_patch = patch.object(settings_service, "UPLOAD_DIR", self.logo_dir)
        self.base_upload_dir_patch.start()
        self.upload_dir_patch.start()
        self.addCleanup(self.base_upload_dir_patch.stop)
        self.addCleanup(self.upload_dir_patch.stop)

    def _make_service(self) -> tuple[SettingsService, AsyncMock]:
        session = AsyncMock()
        session.add = Mock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return SettingsService(session=session), session

    async def test_get_settings_creates_singleton_row_when_missing(self) -> None:
        service, session = self._make_service()
        result = Mock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        settings = await service.get_settings()

        self.assertEqual(settings.id, SINGLETON_ID)
        self.assertEqual(settings.site_name, "Inviter Pro")
        session.add.assert_called_once()
        session.commit.assert_awaited()
        session.refresh.assert_awaited_once()

    async def test_upload_logo_rejects_unsupported_extension(self) -> None:
        service, session = self._make_service()

        with self.assertRaises(HTTPException) as ctx:
            await service.upload_logo(FakeUploadFile("logo.gif", "image/gif", b"gif"))

        self.assertEqual(ctx.exception.status_code, 400)
        session.commit.assert_not_called()

    async def test_upload_logo_rejects_oversized_file(self) -> None:
        service, session = self._make_service()
        service.get_settings = AsyncMock(return_value=SiteSettings(id=SINGLETON_ID))  # type: ignore[method-assign]

        with self.assertRaises(HTTPException) as ctx:
            await service.upload_logo(
                FakeUploadFile("logo.png", "image/png", b"x" * (settings_service.MAX_LOGO_SIZE_BYTES + 1))
            )

        self.assertEqual(ctx.exception.status_code, 413)
        session.commit.assert_not_called()

    async def test_upload_and_delete_logo_updates_settings_and_files(self) -> None:
        service, session = self._make_service()
        settings = SiteSettings(id=SINGLETON_ID, logo_path=None)
        service.get_settings = AsyncMock(return_value=settings)  # type: ignore[method-assign]

        logo_path = await service.upload_logo(FakeUploadFile("logo.png", "image/png", b"png-data"))

        self.assertEqual(logo_path, "uploads/logo/logo.png")
        self.assertEqual(settings.logo_path, "uploads/logo/logo.png")
        self.assertTrue((self.logo_dir / "logo.png").exists())
        session.commit.assert_awaited()

        await service.delete_logo()

        self.assertIsNone(settings.logo_path)
        self.assertFalse((self.logo_dir / "logo.png").exists())
        self.assertGreaterEqual(session.commit.await_count, 2)
