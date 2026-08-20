from __future__ import annotations

import argparse
import asyncio
import getpass
import uuid

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.db import models as _models  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.features.auth.models import User


_password_helper = PasswordHelper()


async def create_admin(email: str, password: str) -> None:
    """Create or promote an administrator with a CLI-owned DB lifecycle.

    Bootstrap intentionally writes the FastAPI Users model directly instead of
    constructing request-scoped FastAPI dependencies/UserManager objects. This
    keeps the production bootstrap independent from ASGI dependency injection
    while using the same FastAPI Users password hasher as normal authentication.

    Supplying a password is authoritative for this explicit administrative
    operation: an existing account is promoted and its password is reset to the
    supplied value. This prevents a bootstrap command from reporting success
    while leaving the operator unable to authenticate with the password they
    just provided.
    """
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Admin email must not be empty")
    if len(password) < 12:
        raise ValueError("Admin password must be at least 12 characters")

    async with AsyncSessionLocal() as session:
        try:
            existing = (
                await session.execute(select(User).where(User.email == normalized_email))
            ).scalar_one_or_none()

            if existing is not None:
                existing.is_active = True
                existing.is_verified = True
                existing.is_superuser = True
                existing.hashed_password = _password_helper.hash(password)
                await session.commit()
                print(f"Promoted/reset admin credentials: {normalized_email}")
                return

            user = User(
                id=uuid.uuid4(),
                email=normalized_email,
                hashed_password=_password_helper.hash(password),
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
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
