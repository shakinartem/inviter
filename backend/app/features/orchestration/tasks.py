from __future__ import annotations

import asyncio
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.features.orchestration.service import OrchestrationService
from app.tasks.celery_app import celery_app


async def _claim_due(limit: int) -> list[UUID]:
    async with AsyncSessionLocal() as session:
        service = OrchestrationService(session)
        return await service.claim_due_jobs(limit=limit)


async def _execute(job_id: UUID) -> dict:
    async with AsyncSessionLocal() as session:
        service = OrchestrationService(session)
        return await service.execute_job(job_id)


@celery_app.task(name="orchestration.dispatch_due")
def dispatch_due_action_jobs(limit: int = 100) -> dict:
    """Claim due jobs transactionally and hand each one to a worker."""
    job_ids = asyncio.run(_claim_due(limit))
    for job_id in job_ids:
        execute_action_job.delay(str(job_id))
    return {"dispatched": len(job_ids)}


@celery_app.task(name="orchestration.execute_action", bind=True, max_retries=1)
def execute_action_job(self, job_id: str) -> dict:
    """Execute one already scheduled action without sleeping inside the worker."""
    try:
        return asyncio.run(_execute(UUID(job_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
