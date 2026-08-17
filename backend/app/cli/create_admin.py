from __future__ import annotations

import argparse
import asyncio
import getpass

from app.core.security import UserManager, get_user_db
from app.db import models as _models  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.features.auth.schemas import UserCreate


async def create_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        user_db_generator = get_user_db(session)
        user_db = await anext(user_db_generator)
        try:
            manager = UserManager(user_db)
            try:
                existing = await manager.get_by_email(email)
            except Exception:
                existing = None

            if existing is not None:
                if getattr(existing, "is_superuser", False):
                    print(f"Admin already exists: {email}")
                    return
                existing.is_active = True
                existing.is_verified = True
                existing.is_superuser = True
                session.add(existing)
                await session.commit()
                print(f"Promoted existing user to admin: {email}")
                return

            await manager.create(
                UserCreate(
                    email=email,
                    password=password,
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                ),
                safe=False,
            )
            await session.commit()
            print(f"Created admin: {email}")
        finally:
            await user_db_generator.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an Inviter administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None, help="Prefer omitting this flag to enter the password interactively")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Admin password must be at least 12 characters")
    asyncio.run(create_admin(args.email.strip().lower(), password))


if __name__ == "__main__":
    main()
