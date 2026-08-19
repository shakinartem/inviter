from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.bootstrap import ensure_dev_admin
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.redis import close_redis, get_redis
from app.db.session import engine
from app.tasks.celery_app import celery_app


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    celery_app.conf.timezone = settings.timezone
    await ensure_dev_admin()
    try:
        yield
    finally:
        await close_redis()
        await engine.dispose()


app = FastAPI(
    title=settings.project_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"service": settings.project_name, "status": "ok"}


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    """Process liveness only; does not touch external dependencies."""
    return {"status": "ok", "environment": settings.environment}


async def _readiness_payload() -> tuple[bool, dict[str, object]]:
    checks: dict[str, str] = {"postgres": "error", "redis": "error"}

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"

    try:
        redis = await get_redis()
        if await redis.ping():
            checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    ready = all(value == "ok" for value in checks.values())
    return ready, {
        "status": "ok" if ready else "not_ready",
        "environment": settings.environment,
        "checks": checks,
    }


@app.get("/health/ready", tags=["health"])
async def readiness():
    """Dependency-aware readiness used by Docker/Caddy deployment checks."""
    ready, payload = await _readiness_payload()
    if ready:
        return payload
    return JSONResponse(status_code=503, content=payload)


@app.get("/health", tags=["health"])
async def healthcheck():
    """Backward-compatible readiness endpoint."""
    return await readiness()
