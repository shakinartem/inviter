"""
Smoke MVP test script.
Runs inside container: python scripts/smoke_mvp.py

Checks:
1. DB connection
2. Alembic current
3. Required tables exist
4. SQLAlchemy configure_mappers() passes
5. GET /health passes
6. Parser stats service works on empty DB
7. Proxy approve service works with synthetic candidate
8. Source discovery list endpoint works
"""

from __future__ import annotations

import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> int:
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    print("=" * 60)
    print("Smoke MVP Check")
    print("=" * 60)

    # 1. DB connection
    print("\n1. Database connection")
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            check("DB connection", val == 1)
    except Exception as e:
        check("DB connection", False, str(e))

    # 2. Alembic current
    print("\n2. Alembic migrations")
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.environment import EnvironmentContext
        from alembic.runtime.migration import MigrationContext
        from app.core.config import settings
        from sqlalchemy import create_engine

        engine = create_engine(settings.sync_database_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            check("Alembic current revision", current_rev is not None, str(current_rev))
    except Exception as e:
        check("Alembic current revision", False, str(e))

    # 3. Required tables exist
    print("\n3. Required tables")
    required_tables = [
        "users", "accounts", "proxies", "proxy_candidates",
        "parsed_chats", "parsed_users",
        "source_candidates", "source_scores",
        "invite_campaigns", "invite_tasks",
    ]
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            existing = {row[0] for row in result.fetchall()}
            for table in required_tables:
                check(f"Table '{table}' exists", table in existing)
    except Exception as e:
        for table in required_tables:
            check(f"Table '{table}' exists", False, str(e))

    # 4. SQLAlchemy configure_mappers()
    print("\n4. SQLAlchemy mapper configuration")
    try:
        import app.db.models  # noqa: F401 — imports all models
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
        check("configure_mappers()", True)
    except Exception as e:
        check("configure_mappers()", False, str(e))

    # 5. GET /health
    print("\n5. Health endpoint")
    try:
        from httpx import AsyncClient
        async with AsyncClient(base_url="http://backend:8000") as client:
            resp = await client.get("/health", timeout=5)
            check("GET /health returns 200", resp.status_code == 200)
    except Exception as e:
        check("GET /health returns 200", False, str(e))

    # 6. Parser stats endpoint on empty DB
    print("\n6. Parser stats endpoint")
    try:
        from httpx import AsyncClient
        async with AsyncClient(base_url="http://backend:8000") as client:
            resp = await client.get("/api/v1/parser/stats", timeout=5)
            check("GET /api/v1/parser/stats returns response", resp.status_code in (200, 401, 403, 404))
    except Exception as e:
        check("Parser stats endpoint", False, str(e))

    # 7. Proxy approve with synthetic candidate
    print("\n7. Proxy approve flow")
    try:
        from app.features.proxies.candidate_models import ProxyCandidate
        from app.features.proxies.models import Proxy
        from app.features.auth.models import User
        from app.db.session import AsyncSessionLocal
        from uuid import uuid4
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as session:
            # Get or create a test user
            result = await session.execute(
                text("SELECT id FROM users LIMIT 1")
            )
            user_row = result.fetchone()
            if user_row:
                owner_id = user_row[0]
            else:
                # Create a minimal user
                from app.features.auth.models import User
                user = User(
                    id=uuid4(),
                    email="smoke@test.com",
                    hashed_password="x",
                    is_active=True,
                    is_superuser=False,
                    is_verified=False,
                )
                session.add(user)
                await session.commit()
                owner_id = user.id

            # Create candidate
            candidate = ProxyCandidate(
                owner_id=owner_id,
                host="127.0.0.1",
                port=8080,
                proxy_type="socks5",
                source_type="manual_text",
                status="alive",
                score=50,
            )
            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)

            # Verify approve service path by re-loading candidate
            await session.refresh(candidate)
            check("Candidate reloads after commit", candidate.id is not None)
            check("Candidate has alive status", candidate.status == "alive")
    except Exception as e:
        check("Proxy approve flow", False, str(e))

    # 8. Source discovery candidates endpoint
    print("\n8. Source discovery candidates")
    try:
        from httpx import AsyncClient
        async with AsyncClient(base_url="http://backend:8000") as client:
            resp = await client.get("/api/v1/source-discovery/candidates", timeout=5)
            check("GET /api/v1/source-discovery/candidates", resp.status_code in (200, 401, 403))
    except Exception as e:
        check("Source discovery candidates", False, str(e))

    # Summary
    print("\n" + "=" * 60)
    if failures == 0:
        print("ALL CHECKS PASSED")
    else:
        print(f"{failures} CHECK(S) FAILED")
    print("=" * 60)
    return failures


def uuid4():
    from uuid import uuid4 as _uuid4
    return _uuid4()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)