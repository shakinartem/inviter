from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import AccountCapacityRiskService


class AccountThroughputForecastService:
    """Forecast campaign throughput using only current conservative account capacity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def forecast(
        self,
        *,
        owner_id: UUID,
        platform: str,
        desired_actions: int,
        campaign_daily_limit: int,
        deadline_days: int | None,
    ) -> dict[str, Any]:
        assessments = await AccountCapacityRiskService(self.session).evaluate_pool(
            owner_id=owner_id,
            platform=platform,
            campaign_daily_limit=campaign_daily_limit,
            persist_snapshots=False,
        )
        eligible = [item for item in assessments if item.eligible]
        quarantined = [item for item in assessments if not item.eligible]
        safe_daily_capacity = sum(item.suggested_daily_capacity for item in eligible)
        queued_jobs = sum(item.queued_jobs for item in assessments)

        # Existing queued work consumes near-term account capacity before new campaign actions.
        # Convert the current queue into a conservative first-day reservation.
        effective_new_daily_capacity = max(safe_daily_capacity - min(queued_jobs, safe_daily_capacity), 0)
        now = datetime.now(timezone.utc)
        warnings: list[str] = []

        if safe_daily_capacity <= 0:
            estimated_days = None
            completion = None
            status = "no_safe_capacity"
            warnings.append("no_eligible_account_capacity")
        else:
            # Queue debt is paid first, then desired actions consume the same safe daily capacity.
            total_work = queued_jobs + desired_actions
            estimated_days = round(total_work / safe_daily_capacity, 2)
            completion = now + timedelta(days=estimated_days)
            status = "ready"

        required_daily = None
        shortfall = 0
        additional_accounts = 0
        if deadline_days is not None:
            required_daily = math.ceil((queued_jobs + desired_actions) / deadline_days)
            shortfall = max(required_daily - safe_daily_capacity, 0)
            if shortfall > 0:
                status = "capacity_shortfall" if safe_daily_capacity > 0 else "no_safe_capacity"
                additional_accounts = math.ceil(shortfall / max(campaign_daily_limit, 1))
                warnings.append("deadline_requires_more_safe_capacity")

        if quarantined:
            warnings.append("some_accounts_are_quarantined")
        if queued_jobs:
            warnings.append("existing_queue_reduces_near_term_capacity")
        if not warnings:
            warnings.append("current_safe_capacity_covers_requested_workload")

        return {
            "platform": platform,
            "desired_actions": desired_actions,
            "campaign_daily_limit": campaign_daily_limit,
            "eligible_accounts": len(eligible),
            "quarantined_accounts": len(quarantined),
            "safe_daily_capacity": safe_daily_capacity,
            "queued_jobs": queued_jobs,
            "effective_new_daily_capacity": effective_new_daily_capacity,
            "estimated_days": estimated_days,
            "estimated_completion_at": completion,
            "deadline_days": deadline_days,
            "required_daily_capacity_for_deadline": required_daily,
            "daily_capacity_shortfall": shortfall,
            "additional_full_health_accounts_needed": additional_accounts,
            "status": status,
            "warnings": warnings,
        }
