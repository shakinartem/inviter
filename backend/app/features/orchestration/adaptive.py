from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import AccountCapacityAssessment, AccountCapacityRiskService
from app.features.accounts.models import Account
from app.features.inviter.models import InviteCampaign
from app.features.orchestration.adaptive_models import ActionAssignmentEvent
from app.features.orchestration.models import ActionJob
from app.features.orchestration.service import OrchestrationService


POLICY_VERSION = "adaptive-execution-v1"
MOVABLE_STATUSES = {"planned"}
ACTIVE_QUEUE_STATUSES = {"planned", "dispatched", "processing", "retry_wait"}


@dataclass(slots=True)
class AdaptiveMove:
    job_id: UUID
    campaign_id: UUID
    from_account_id: UUID
    from_account_label: str
    to_account_id: UUID
    to_account_label: str
    previous_scheduled_at: datetime
    new_scheduled_at: datetime
    reason: str
    target_health_score: float
    target_daily_capacity: int

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdaptivePlan:
    source_account_id: UUID
    source_account_label: str
    reason: str
    movable_jobs: int
    moved_jobs: int
    untouched_started_or_retry_jobs: int
    no_safe_target_jobs: int
    target_accounts: int
    latest_reassigned_at: datetime | None
    moves: list[AdaptiveMove]

    def public_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "moves": [move.public_dict() for move in self.moves],
        }


class AdaptiveExecutionService:
    """Reassign not-yet-attempted jobs away from a degraded account.

    Safety invariants:
    - only `planned` jobs with attempts == 0 are movable;
    - jobs never move earlier than their existing scheduled time;
    - target accounts must already belong to the campaign's job pool;
    - target account capacity is capped by the risk engine and campaign warmup;
    - retry/started jobs stay pinned to avoid ambiguous duplicate actions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def preview(
        self,
        *,
        owner_id: UUID,
        source_account_id: UUID,
        campaign_id: UUID | None = None,
        reason: str = "manual_preview",
        max_jobs: int = 500,
    ) -> AdaptivePlan:
        return await self._build_plan(
            owner_id=owner_id,
            source_account_id=source_account_id,
            campaign_id=campaign_id,
            reason=reason,
            max_jobs=max_jobs,
            apply=False,
        )

    async def rebalance_account(
        self,
        *,
        owner_id: UUID,
        source_account_id: UUID,
        campaign_id: UUID | None = None,
        reason: str = "account_degraded",
        max_jobs: int = 500,
    ) -> AdaptivePlan:
        return await self._build_plan(
            owner_id=owner_id,
            source_account_id=source_account_id,
            campaign_id=campaign_id,
            reason=reason,
            max_jobs=max_jobs,
            apply=True,
        )

    async def events(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        account_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ActionAssignmentEvent]:
        stmt = select(ActionAssignmentEvent).where(ActionAssignmentEvent.owner_id == owner_id)
        if campaign_id is not None:
            stmt = stmt.where(ActionAssignmentEvent.campaign_id == campaign_id)
        if account_id is not None:
            stmt = stmt.where(
                (ActionAssignmentEvent.from_account_id == account_id)
                | (ActionAssignmentEvent.to_account_id == account_id)
            )
        result = await self.session.execute(
            stmt.order_by(ActionAssignmentEvent.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def _build_plan(
        self,
        *,
        owner_id: UUID,
        source_account_id: UUID,
        campaign_id: UUID | None,
        reason: str,
        max_jobs: int,
        apply: bool,
    ) -> AdaptivePlan:
        max_jobs = max(1, min(int(max_jobs), 2_000))
        source = (
            await self.session.execute(
                select(Account).where(
                    Account.id == source_account_id,
                    Account.owner_id == owner_id,
                    Account.platform == "telegram",
                )
            )
        ).scalar_one_or_none()
        if source is None:
            raise ValueError("Source Telegram account not found")

        movable_stmt = (
            select(ActionJob)
            .join(InviteCampaign, InviteCampaign.id == ActionJob.campaign_id)
            .where(
                ActionJob.owner_id == owner_id,
                ActionJob.account_id == source_account_id,
                ActionJob.platform == "telegram",
                ActionJob.status == "planned",
                ActionJob.attempts == 0,
                InviteCampaign.status == "active",
            )
            .order_by(ActionJob.scheduled_at.asc(), ActionJob.id.asc())
            .limit(max_jobs)
        )
        if campaign_id is not None:
            movable_stmt = movable_stmt.where(ActionJob.campaign_id == campaign_id)
        movable = list((await self.session.execute(movable_stmt)).scalars().all())

        pinned_stmt = select(func.count(ActionJob.id)).where(
            ActionJob.owner_id == owner_id,
            ActionJob.account_id == source_account_id,
            ActionJob.platform == "telegram",
            (ActionJob.status == "retry_wait") | (ActionJob.attempts > 0),
            ActionJob.status.notin_(["success", "failed", "cancelled"]),
        )
        if campaign_id is not None:
            pinned_stmt = pinned_stmt.where(ActionJob.campaign_id == campaign_id)
        pinned = int((await self.session.execute(pinned_stmt)).scalar() or 0)

        if not movable:
            return AdaptivePlan(
                source_account_id=source.id,
                source_account_label=source.label,
                reason=reason,
                movable_jobs=0,
                moved_jobs=0,
                untouched_started_or_retry_jobs=pinned,
                no_safe_target_jobs=0,
                target_accounts=0,
                latest_reassigned_at=None,
                moves=[],
            )

        campaign_ids = sorted({job.campaign_id for job in movable}, key=str)
        campaigns_result = await self.session.execute(
            select(InviteCampaign).where(InviteCampaign.id.in_(campaign_ids))
        )
        campaigns = {item.id: item for item in campaigns_result.scalars().all()}

        plans: list[AdaptiveMove] = []
        no_safe_target = 0
        target_ids_seen: set[UUID] = set()
        now = datetime.now(timezone.utc)

        # Work campaign-by-campaign because safe limits and delay policies differ.
        jobs_by_campaign: dict[UUID, list[ActionJob]] = defaultdict(list)
        for job in movable:
            jobs_by_campaign[job.campaign_id].append(job)

        for current_campaign_id, jobs in jobs_by_campaign.items():
            campaign = campaigns.get(current_campaign_id)
            if campaign is None:
                no_safe_target += len(jobs)
                continue

            pool_result = await self.session.execute(
                select(ActionJob.account_id)
                .where(
                    ActionJob.owner_id == owner_id,
                    ActionJob.campaign_id == current_campaign_id,
                    ActionJob.platform == "telegram",
                )
                .distinct()
            )
            campaign_pool = {
                account_id
                for account_id in pool_result.scalars().all()
                if account_id != source_account_id
            }
            if not campaign_pool:
                no_safe_target += len(jobs)
                continue

            risk_service = AccountCapacityRiskService(self.session)
            assessments = await risk_service.evaluate_pool(
                owner_id=owner_id,
                platform="telegram",
                campaign_daily_limit=max(int(campaign.daily_limit_per_account), 1),
                account_ids=list(campaign_pool),
                persist_snapshots=False,
            )
            eligible_assessments = {
                item.account_id: item for item in assessments if item.eligible and item.suggested_daily_capacity > 0
            }
            if not eligible_assessments:
                no_safe_target += len(jobs)
                continue

            accounts_result = await self.session.execute(
                select(Account).where(Account.id.in_(eligible_assessments.keys()))
            )
            accounts = {item.id: item for item in accounts_result.scalars().all()}
            target_ids_seen.update(accounts)

            limits: dict[UUID, int] = {}
            for account_id, assessment in eligible_assessments.items():
                account = accounts.get(account_id)
                if account is None:
                    continue
                warmup_limit = OrchestrationService._effective_daily_limit(account, campaign, now)
                limits[account_id] = max(
                    min(int(assessment.suggested_daily_capacity), int(warmup_limit)),
                    1,
                )
            if not limits:
                no_safe_target += len(jobs)
                continue

            state = await self._queue_state(account_ids=list(limits), now=now)
            sequence_counts = state["sequence_counts"]
            daily_counts = state["daily_counts"]
            next_at = state["next_at"]

            for job in jobs:
                candidates: list[tuple[datetime, float, UUID]] = []
                for target_id, daily_limit in limits.items():
                    assessment = eligible_assessments[target_id]
                    desired = max(
                        self._aware(job.scheduled_at),
                        next_at.get(target_id, now),
                    )
                    if sequence_counts[target_id] > 0:
                        desired += timedelta(seconds=max(int(campaign.invite_delay_min), 1))
                    if (
                        int(campaign.pause_after_every) > 0
                        and sequence_counts[target_id] > 0
                        and sequence_counts[target_id] % int(campaign.pause_after_every) == 0
                    ):
                        desired += timedelta(minutes=max(int(campaign.pause_duration_min), 0))
                    slot = self._next_capacity_slot(
                        desired_at=desired,
                        daily_limit=daily_limit,
                        daily_counts=daily_counts[target_id],
                    )
                    candidates.append((slot, -float(assessment.health_score), target_id))

                if not candidates:
                    no_safe_target += 1
                    continue
                new_scheduled_at, _, target_id = min(candidates)
                assessment = eligible_assessments[target_id]
                target = accounts[target_id]
                move = AdaptiveMove(
                    job_id=job.id,
                    campaign_id=job.campaign_id,
                    from_account_id=source.id,
                    from_account_label=source.label,
                    to_account_id=target_id,
                    to_account_label=target.label,
                    previous_scheduled_at=self._aware(job.scheduled_at),
                    new_scheduled_at=new_scheduled_at,
                    reason=reason,
                    target_health_score=float(assessment.health_score),
                    target_daily_capacity=limits[target_id],
                )
                plans.append(move)
                daily_counts[target_id][new_scheduled_at.date()] += 1
                sequence_counts[target_id] += 1
                next_at[target_id] = new_scheduled_at

        if apply and plans:
            applied: list[AdaptiveMove] = []
            for move in plans:
                locked = (
                    await self.session.execute(
                        select(ActionJob)
                        .where(
                            ActionJob.id == move.job_id,
                            ActionJob.owner_id == owner_id,
                            ActionJob.account_id == source_account_id,
                            ActionJob.status == "planned",
                            ActionJob.attempts == 0,
                        )
                        .with_for_update(skip_locked=True)
                    )
                ).scalar_one_or_none()
                if locked is None:
                    continue

                payload = dict(locked.payload or {})
                payload["account_label"] = move.to_account_label
                payload["adaptive_execution"] = {
                    "policy_version": POLICY_VERSION,
                    "reason": reason,
                    "from_account_id": str(move.from_account_id),
                    "to_account_id": str(move.to_account_id),
                    "reassigned_at": now.isoformat(),
                }
                locked.account_id = move.to_account_id
                locked.scheduled_at = move.new_scheduled_at
                locked.payload = payload
                self.session.add(
                    ActionAssignmentEvent(
                        owner_id=owner_id,
                        campaign_id=move.campaign_id,
                        action_job_id=move.job_id,
                        from_account_id=move.from_account_id,
                        to_account_id=move.to_account_id,
                        reason=reason[:64],
                        policy_version=POLICY_VERSION,
                        previous_scheduled_at=move.previous_scheduled_at,
                        new_scheduled_at=move.new_scheduled_at,
                        details={
                            "target_health_score": move.target_health_score,
                            "target_daily_capacity": move.target_daily_capacity,
                            "invariant": "attempts_zero_only",
                        },
                    )
                )
                applied.append(move)
            await self.session.commit()
            plans = applied

        latest = max((item.new_scheduled_at for item in plans), default=None)
        return AdaptivePlan(
            source_account_id=source.id,
            source_account_label=source.label,
            reason=reason,
            movable_jobs=len(movable),
            moved_jobs=len(plans),
            untouched_started_or_retry_jobs=pinned,
            no_safe_target_jobs=no_safe_target + max(len(movable) - len(plans) - no_safe_target, 0),
            target_accounts=len(target_ids_seen),
            latest_reassigned_at=latest,
            moves=plans,
        )

    async def _queue_state(self, *, account_ids: list[UUID], now: datetime) -> dict[str, Any]:
        result = await self.session.execute(
            select(ActionJob).where(
                ActionJob.account_id.in_(account_ids),
                ActionJob.status.in_(ACTIVE_QUEUE_STATUSES),
            )
        )
        jobs = list(result.scalars().all())
        daily_counts: dict[UUID, dict[object, int]] = {
            account_id: defaultdict(int) for account_id in account_ids
        }
        sequence_counts: dict[UUID, int] = defaultdict(int)
        next_at: dict[UUID, datetime] = {account_id: now for account_id in account_ids}
        for job in jobs:
            scheduled = self._aware(job.next_attempt_at or job.scheduled_at)
            daily_counts[job.account_id][scheduled.date()] += 1
            sequence_counts[job.account_id] += 1
            if scheduled > next_at[job.account_id]:
                next_at[job.account_id] = scheduled
        return {
            "daily_counts": daily_counts,
            "sequence_counts": sequence_counts,
            "next_at": next_at,
        }

    @staticmethod
    def _next_capacity_slot(
        *,
        desired_at: datetime,
        daily_limit: int,
        daily_counts: dict[object, int],
    ) -> datetime:
        candidate = desired_at
        daily_limit = max(int(daily_limit), 1)
        guard = 0
        while daily_counts[candidate.date()] >= daily_limit:
            candidate = (candidate + timedelta(days=1)).replace(
                hour=desired_at.hour,
                minute=desired_at.minute,
                second=desired_at.second,
                microsecond=desired_at.microsecond,
            )
            guard += 1
            if guard > 370:
                raise RuntimeError("Could not find adaptive execution capacity within one year")
        return candidate

    @staticmethod
    def required_pool_for_failover(*, movable_jobs: int, safe_daily_capacity: int) -> int | None:
        if movable_jobs <= 0:
            return 0
        if safe_daily_capacity <= 0:
            return None
        return ceil(movable_jobs / safe_daily_capacity)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
