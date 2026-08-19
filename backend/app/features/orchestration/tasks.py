from __future__ import annotations

import asyncio
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.features.connections.orchestration import ConnectionAwareOrchestrationService
from app.features.orchestration.preflight_learning import CampaignPreflightLearningService
from app.features.orchestration.sla_calibration import ExecutionSLACalibrationService
from app.tasks.celery_app import celery_app


async def _claim_due(limit: int) -> list[UUID]:
    async with AsyncSessionLocal() as session:
        service = ConnectionAwareOrchestrationService(session)
        return await service.claim_due_jobs(limit=limit)


async def _execute(job_id: UUID) -> dict:
    async with AsyncSessionLocal() as session:
        service = ConnectionAwareOrchestrationService(session)
        return await service.execute_job(job_id)


async def _finalize_sla(limit: int) -> dict:
    async with AsyncSessionLocal() as session:
        result = await ExecutionSLACalibrationService(session).finalize_mature_forecasts(
            owner_id=None,
            limit=limit,
        )
        return result.model_dump(mode="json")


async def _finalize_preflight_decisions(limit: int) -> dict:
    async with AsyncSessionLocal() as session:
        result = await CampaignPreflightLearningService(session).finalize_mature(
            owner_id=None,
            limit=limit,
        )
        return result.model_dump(mode="json")


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


@celery_app.task(name="orchestration.finalize_execution_sla")
def finalize_execution_sla(limit: int = 250) -> dict:
    """Label matured execution forecasts without blocking request workers."""
    return asyncio.run(_finalize_sla(limit))


@celery_app.task(name="orchestration.finalize_preflight_decisions")
def finalize_preflight_decisions(limit: int = 250) -> dict:
    """Attach factual outcomes to matured launch-time preflight snapshots."""
    return asyncio.run(_finalize_preflight_decisions(limit))
