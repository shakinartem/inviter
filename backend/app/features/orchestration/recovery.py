from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.models import ActionJob


async def recover_stale_action_jobs(
    session: AsyncSession,
    *,
    dispatch_lease_seconds: int = 120,
    processing_timeout_seconds: int = 900,
) -> dict[str, int]:
    """Recover DB orchestration state after worker/broker crashes.

    `dispatched` with zero attempts is safe to requeue because execute_job has not
    crossed the processing boundary. A stale `processing` job is deliberately
    not retried: an external action may have happened before the worker died, so
    automatic replay could duplicate the side effect.
    """

    now = datetime.now(timezone.utc)
    dispatch_cutoff = now - timedelta(seconds=max(dispatch_lease_seconds, 30))
    processing_cutoff = now - timedelta(seconds=max(processing_timeout_seconds, 120))

    safe = await session.execute(
        update(ActionJob)
        .where(
            ActionJob.status == "dispatched",
            ActionJob.attempts == 0,
            ActionJob.updated_at <= dispatch_cutoff,
        )
        .values(
            status="planned",
            result_code="DISPATCH_LEASE_RECOVERED",
            result_message="Broker/worker dispatch lease expired before execution started",
            updated_at=now,
        )
    )

    ambiguous = await session.execute(
        update(ActionJob)
        .where(
            ActionJob.status == "processing",
            ActionJob.attempts > 0,
            ActionJob.updated_at <= processing_cutoff,
        )
        .values(
            status="failed",
            result_code="AMBIGUOUS_EXECUTION",
            result_message=(
                "Worker disappeared after execution started; action is not replayed automatically "
                "because the external side effect may already have occurred"
            ),
            finished_at=now,
            next_attempt_at=None,
            updated_at=now,
        )
    )

    await session.commit()
    return {
        "requeued_dispatched": int(safe.rowcount or 0),
        "failed_ambiguous_processing": int(ambiguous.rowcount or 0),
    }
