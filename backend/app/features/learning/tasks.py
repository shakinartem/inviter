from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.features.learning.observer import AutomaticOutcomeObserver
from app.tasks.celery_app import celery_app


async def _scan_due(
    limit_campaigns: int,
    lookback_days: int,
    message_limit: int,
) -> dict:
    async with AsyncSessionLocal() as session:
        observer = AutomaticOutcomeObserver(session)
        return await observer.scan_due(
            limit_campaigns=limit_campaigns,
            lookback_days=lookback_days,
            message_limit=message_limit,
        )


@celery_app.task(name="learning.observe_engagement")
def observe_engagement(
    limit_campaigns: int = 50,
    lookback_days: int = 30,
    message_limit: int = 5_000,
) -> dict:
    """Batch-read destination activity and create post-action engagement labels."""
    return asyncio.run(
        _scan_due(
            limit_campaigns=limit_campaigns,
            lookback_days=lookback_days,
            message_limit=message_limit,
        )
    )
