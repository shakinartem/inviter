from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    """Get or create the shared Redis connection pool."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return _redis


async def close_redis() -> None:
    """Close Redis connections during application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
