from __future__ import annotations

from loguru import logger

from app.core.config import settings
from app.core.security import UserManager, get_user_db
from app.db import models as _models  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.features.auth.schemas import UserCreate


async def ensure_dev_admin() -> None:
    if settings.environment.lower() != "development":
        return

    async with AsyncSessionLocal() as session:
        user_db_generator = get_user_db(session)
        user_db = await anext(user_db_generator)

        try:
            manager = UserManager(user_db)
            try:
                await manager.get_by_email(settings.dev_admin_email)
                return
            except Exception:
                await manager.create(
                    UserCreate(
                        email=settings.dev_admin_email,
                        password=settings.dev_admin_password,
                        is_active=True,
                        is_superuser=True,
                        is_verified=True,
                    ),
                    safe=False,
                )
                await session.commit()
                logger.info("Created development admin user {}", settings.dev_admin_email)
        finally:
            await user_db_generator.aclose()
