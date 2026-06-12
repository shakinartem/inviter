from __future__ import annotations

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    telegram_user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class UserCreate(schemas.BaseUserCreate):
    telegram_user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    telegram_user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
