from __future__ import annotations

import argparse
import asyncio
import getpass

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select

from app.core.security import UserManager
from app.db import models as _models  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.features.auth.models import User
from app.features.auth.schemas import UserCreate


async def create_admin(email: str, password: str) -> None:
    """Create or promote an administrator using a direct CLI-safe DB lifecycle.

    This deliberately does not manually drive FastAPI dependency generators.
    The CLI owns one AsyncSession, constructs the FastAPI Users adapter directly,
    and lets real exceptions propagate so deployment tooling never mistakes a
    failed bootstrap for an existing user.
    """
    normalized_email = email.strip().lower()

    async with AsyncSessionLocal() as session:
        try:
            existing = (
                await session.execute(select(User).where(User.email == normalized_email))
            ).scalar_one_or_none()

            if existing is not None:
                changed = False
                if not existing.is_active:
                    existing.is_active = True
                    changed = True
                if not existing.is_verified:
                    existing.is_verified = True
                    changed = True
                if not existing.is_superuser:
                    existing.is_superuser = True
                    changed = True

                if changed:
                    session.add(existing)
                    await session.commit()
                    print(f"Promoted existing user to admin: {normalized_email}")
                else:
                    print(f"Admin already exists: {normalized_email}")
                return

            user_db = SQLAlchemyUserDatabase(session, User)
            manager = UserManager(user_db)
            await manager.create(
                UserCreate(
                    email=normalized_email,
                    password=password,
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                ),
                safe=False,
            )
            await session.commit()
            print(f"Created admin: {normalized_email}")
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an Inviter administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password",
        default=None,
        help="Prefer omitting this flag to enter the password interactively",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Admin password must be at least 12 characters")
    asyncio.run(create_admin(args.email, password))


if __name__ == "__main__":
    main()
