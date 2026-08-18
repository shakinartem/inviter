from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity_models import AccountCapacitySnapshot
from app.features.accounts.models import Account
from app.features.orchestration.models import ActionJob


POLICY_VERSION = "account-risk-v1"

# Errors that say something about the account/transport itself.
ACCOUNT_LEVEL_CODES = {
    "FLOOD_WAIT",
    "PEER_FLOOD",
    "CONNECTOR_ERROR",
    "ACCOUNT_UNAVAILABLE",
}

# These primarily describe the individual target and must not poison account health.
TARGET_LEVEL_CODES = {
    "PRIVACY_RESTRICTED",
    "NOT_MUTUAL_CONTACT",
    "USER_BLOCKED",
    "USER_BANNED",
}

# These describe the selected destination or permissions, not global account health.
DESTINATION_LEVEL_CODES = {
    "ADMIN_REQUIRED",
    "CHANNEL_PRIVATE",
    "WRITE_FORBIDDEN",
    "UNSUPPORTED_DESTINATION",
}

HARD_COOLDOWN_CODES = {"FLOOD_WAIT", "PEER_FLOOD"}
ACTIVE_QUEUE_STATUSES = {"planned", "dispatched", "processing", "retry_wait"}


@dataclass(slots=True)
class AccountCapacityAssessment:
    account_id: UUID
    label: str
    platform: str
    status: str
    health_score: float
    risk_score: float
    capacity_multiplier: float
    suggested_daily_capacity: int
    campaign_daily_limit: int
    attempts_24h: int
    successes_24h: int
    account_errors_24h: int
    target_errors_24h: int
    floodwaits_24h: int
    peer_floods_7d: int
    connector_errors_24h: int
    queued_jobs: int
    eligible: bool
    next_safe_at: datetime | None
    reasons: list[str]
    calculated_at: datetime

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccountCapacityRiskService:
    """Conservative account health and safe-capacity controller.

    The policy never raises a campaign/platform limit. It can only reduce the
    effective daily capacity, defer work, or quarantine an account after a
    platform safety signal.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate_pool(
        self,
        *,
        owner_id: UUID,
        platform: str = "telegram",
        campaign_daily_limit: int = 30,
        account_ids: list[UUID] | None = None,
        persist_snapshots: bool = False,
    ) -> list[AccountCapacityAssessment]:
        now = datetime.now(timezone.utc)
        await self.release_expired_cooldowns(owner_id=owner_id, now=now)

        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.platform == platform,
            Account.is_active.is_(True),
        )
        if account_ids:
            stmt = stmt.where(Account.id.in_(account_ids))
        result = await self.session.execute(stmt.order_by(Account.label.asc()))
        accounts = list(result.scalars().all())
        if not accounts:
            return []

        metrics = await self._metrics([account.id for account in accounts], now=now)
        assessments = [
            self.assess(
                account,
                metrics=metrics.get(account.id, {}),
                campaign_daily_limit=campaign_daily_limit,
                now=now,
            )
            for account in accounts
        ]

        for account, assessment in zip(accounts, assessments):
            # Keep the operational account health field synchronized with the
            # latest deterministic assessment. Do not mutate manual labels/notes.
            account.health_score = assessment.health_score
            if persist_snapshots:
                self.session.add(
                    AccountCapacitySnapshot(
                        owner_id=owner_id,
                        account_id=account.id,
                        platform=account.platform,
                        health_score=assessment.health_score,
                        risk_score=assessment.risk_score,
                        capacity_multiplier=assessment.capacity_multiplier,
                        suggested_daily_capacity=assessment.suggested_daily_capacity,
                        attempts_24h=assessment.attempts_24h,
                        successes_24h=assessment.successes_24h,
                        account_errors_24h=assessment.account_errors_24h,
                        target_errors_24h=assessment.target_errors_24h,
                        floodwaits_24h=assessment.floodwaits_24h,
                        peer_floods_7d=assessment.peer_floods_7d,
                        connector_errors_24h=assessment.connector_errors_24h,
                        queued_jobs=assessment.queued_jobs,
                        eligible=assessment.eligible,
                        next_safe_at=assessment.next_safe_at,
                        reasons=assessment.reasons,
                        calculated_at=assessment.calculated_at,
                    )
                )
        await self.session.commit()
        return assessments

    @classmethod
    def assess(
        cls,
        account: Account,
        *,
        metrics: dict[str, int],
        campaign_daily_limit: int,
        now: datetime,
    ) -> AccountCapacityAssessment:
        limit = max(int(campaign_daily_limit), 1)
        attempts_24h = int(metrics.get("attempts_24h", 0))
        successes_24h = int(metrics.get("successes_24h", 0))
        account_errors_24h = int(metrics.get("account_errors_24h", 0))
        target_errors_24h = int(metrics.get("target_errors_24h", 0))
        floodwaits_24h = int(metrics.get("floodwaits_24h", 0))
        peer_floods_7d = int(metrics.get("peer_floods_7d", 0))
        connector_errors_24h = int(metrics.get("connector_errors_24h", 0))
        queued_jobs = int(metrics.get("queued_jobs", 0))

        reasons: list[str] = []
        risk = 0.0
        next_safe_at: datetime | None = None
        hard_ineligible = False

        cooldown_until = cls._aware_optional(account.cooldown_until)
        banned_until = cls._aware_optional(account.banned_until)

        if not account.is_active or account.status in {"inactive", "banned", "error"}:
            hard_ineligible = True
            risk = 100.0
            reasons.append(f"account_status_{account.status}")
        if banned_until and banned_until > now:
            hard_ineligible = True
            risk = 100.0
            next_safe_at = banned_until
            reasons.append("banned_until_future")
        if cooldown_until and cooldown_until > now:
            hard_ineligible = True
            risk = max(risk, 95.0)
            next_safe_at = max(next_safe_at, cooldown_until) if next_safe_at else cooldown_until
            reasons.append("cooldown_active")

        if peer_floods_7d:
            risk += min(80.0, 60.0 + 10.0 * max(peer_floods_7d - 1, 0))
            reasons.append("recent_peer_flood")
        if floodwaits_24h:
            risk += min(60.0, 25.0 * floodwaits_24h)
            reasons.append("recent_flood_wait")
        if connector_errors_24h:
            risk += min(30.0, 8.0 * connector_errors_24h)
            reasons.append("recent_connector_errors")

        if attempts_24h >= 5:
            account_error_rate = account_errors_24h / max(attempts_24h, 1)
            if account_error_rate > 0.20:
                risk += min(25.0, (account_error_rate - 0.20) * 60.0)
                reasons.append("elevated_account_error_rate")

        risk = min(max(risk, 0.0), 100.0)
        health = round(100.0 - risk, 2)

        if risk < 20:
            risk_multiplier = 1.0
        elif risk < 40:
            risk_multiplier = 0.75
        elif risk < 60:
            risk_multiplier = 0.50
        elif risk < 80:
            risk_multiplier = 0.25
        else:
            risk_multiplier = 0.0

        # Connection tenure is only a conservative proxy for maturity. It never
        # increases capacity above the campaign limit.
        tenure_multiplier = 1.0
        if account.created_at:
            age_days = max((now - cls._aware(account.created_at)).days, 0)
            if age_days < 2:
                tenure_multiplier = 0.35
                reasons.append("new_connection_first_48h")
            elif age_days < 7:
                tenure_multiplier = 0.50
                reasons.append("new_connection_first_week")
            elif age_days < 14:
                tenure_multiplier = 0.75
                reasons.append("connection_under_two_weeks")

        capacity_multiplier = min(risk_multiplier, tenure_multiplier)
        if hard_ineligible:
            capacity_multiplier = 0.0
        suggested = min(limit, max(int(limit * capacity_multiplier), 0))
        eligible = suggested > 0 and not hard_ineligible and account.status in {"active", "idle"}

        if queued_jobs > max(suggested * 2, 20):
            reasons.append("queue_backlog_high")

        if not reasons:
            reasons.append("healthy_recent_account_signals")

        return AccountCapacityAssessment(
            account_id=account.id,
            label=account.label,
            platform=account.platform,
            status=account.status,
            health_score=health,
            risk_score=round(risk, 2),
            capacity_multiplier=round(capacity_multiplier, 3),
            suggested_daily_capacity=suggested,
            campaign_daily_limit=limit,
            attempts_24h=attempts_24h,
            successes_24h=successes_24h,
            account_errors_24h=account_errors_24h,
            target_errors_24h=target_errors_24h,
            floodwaits_24h=floodwaits_24h,
            peer_floods_7d=peer_floods_7d,
            connector_errors_24h=connector_errors_24h,
            queued_jobs=queued_jobs,
            eligible=eligible,
            next_safe_at=next_safe_at,
            reasons=reasons,
            calculated_at=now,
        )

    async def apply_action_outcome(
        self,
        *,
        account: Account,
        outcome: dict[str, Any],
        now: datetime | None = None,
    ) -> datetime | None:
        """Apply only account-level safety effects from one connector outcome.

        Returns a newly imposed cooldown timestamp when future work should be
        shifted. Target/destination-specific outcomes intentionally do not reduce
        account health.
        """
        now = now or datetime.now(timezone.utc)
        code = str(outcome.get("code") or "UNKNOWN").upper()
        cooldown_until: datetime | None = None

        if outcome.get("ok"):
            account.health_score = min(float(account.health_score or 100.0) + 1.0, 100.0)
            return None

        if code == "FLOOD_WAIT":
            seconds = max(int(outcome.get("retry_after") or 60), 1)
            cooldown_until = now + timedelta(seconds=seconds)
            account.total_floodwaits = (account.total_floodwaits or 0) + 1
            account.health_score = min(float(account.health_score or 100.0), 55.0)
            account.status = "cooldown"
            account.status_message = f"Platform cooldown after FLOOD_WAIT until {cooldown_until.isoformat()}"
        elif code == "PEER_FLOOD":
            seconds = max(int(outcome.get("retry_after") or 3600), 3600)
            cooldown_until = now + timedelta(seconds=seconds)
            account.total_floodwaits = (account.total_floodwaits or 0) + 1
            account.health_score = min(float(account.health_score or 100.0), 20.0)
            account.status = "cooldown"
            account.status_message = f"Safety quarantine after PEER_FLOOD until {cooldown_until.isoformat()}"
        elif code == "CONNECTOR_ERROR":
            account.health_score = max(float(account.health_score or 100.0) - 12.0, 0.0)
        elif code == "ACCOUNT_UNAVAILABLE":
            account.health_score = max(float(account.health_score or 100.0) - 20.0, 0.0)
        elif code in TARGET_LEVEL_CODES or code in DESTINATION_LEVEL_CODES:
            return None

        if cooldown_until:
            current = self._aware_optional(account.cooldown_until)
            if current and current > cooldown_until:
                cooldown_until = current
            account.cooldown_until = cooldown_until
            await self.shift_future_queue(account_id=account.id, not_before=cooldown_until, now=now)
        return cooldown_until

    async def shift_future_queue(
        self,
        *,
        account_id: UUID,
        not_before: datetime,
        now: datetime | None = None,
    ) -> int:
        """Shift pending work by the cooldown duration while preserving spacing."""
        now = now or datetime.now(timezone.utc)
        not_before = self._aware(not_before)
        delta = max(not_before - now, timedelta(seconds=0))
        if delta <= timedelta(0):
            return 0

        result = await self.session.execute(
            update(ActionJob)
            .where(
                ActionJob.account_id == account_id,
                ActionJob.status.in_(["planned", "retry_wait"]),
            )
            .values(
                scheduled_at=ActionJob.scheduled_at + delta,
                next_attempt_at=case(
                    (ActionJob.next_attempt_at.is_not(None), ActionJob.next_attempt_at + delta),
                    else_=None,
                ),
            )
        )
        return int(result.rowcount or 0)

    async def release_expired_cooldowns(
        self,
        *,
        owner_id: UUID | None = None,
        now: datetime | None = None,
    ) -> int:
        now = now or datetime.now(timezone.utc)
        clauses = [
            Account.status == "cooldown",
            Account.cooldown_until.is_not(None),
            Account.cooldown_until <= now,
            Account.is_active.is_(True),
        ]
        if owner_id is not None:
            clauses.append(Account.owner_id == owner_id)
        result = await self.session.execute(
            update(Account)
            .where(*clauses)
            .values(status="active", status_message=None, cooldown_until=None)
        )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def history(
        self,
        *,
        owner_id: UUID,
        account_id: UUID,
        limit: int = 100,
    ) -> list[AccountCapacitySnapshot]:
        result = await self.session.execute(
            select(AccountCapacitySnapshot)
            .where(
                AccountCapacitySnapshot.owner_id == owner_id,
                AccountCapacitySnapshot.account_id == account_id,
            )
            .order_by(AccountCapacitySnapshot.calculated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _metrics(self, account_ids: list[UUID], *, now: datetime) -> dict[UUID, dict[str, int]]:
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)

        result = await self.session.execute(
            select(
                ActionJob.account_id,
                func.count(ActionJob.id).filter(ActionJob.started_at >= day_ago).label("attempts_24h"),
                func.count(ActionJob.id).filter(
                    ActionJob.status == "success", ActionJob.finished_at >= day_ago
                ).label("successes_24h"),
                func.count(ActionJob.id).filter(
                    ActionJob.result_code.in_(ACCOUNT_LEVEL_CODES), ActionJob.updated_at >= day_ago
                ).label("account_errors_24h"),
                func.count(ActionJob.id).filter(
                    ActionJob.result_code.in_(TARGET_LEVEL_CODES), ActionJob.updated_at >= day_ago
                ).label("target_errors_24h"),
                func.count(ActionJob.id).filter(
                    ActionJob.result_code == "FLOOD_WAIT", ActionJob.updated_at >= day_ago
                ).label("floodwaits_24h"),
                func.count(ActionJob.id).filter(
                    ActionJob.result_code == "PEER_FLOOD", ActionJob.updated_at >= week_ago
                ).label("peer_floods_7d"),
                func.count(ActionJob.id).filter(
                    ActionJob.result_code == "CONNECTOR_ERROR", ActionJob.updated_at >= day_ago
                ).label("connector_errors_24h"),
            )
            .where(ActionJob.account_id.in_(account_ids), ActionJob.updated_at >= week_ago)
            .group_by(ActionJob.account_id)
        )
        metrics: dict[UUID, dict[str, int]] = {
            row.account_id: {
                "attempts_24h": int(row.attempts_24h or 0),
                "successes_24h": int(row.successes_24h or 0),
                "account_errors_24h": int(row.account_errors_24h or 0),
                "target_errors_24h": int(row.target_errors_24h or 0),
                "floodwaits_24h": int(row.floodwaits_24h or 0),
                "peer_floods_7d": int(row.peer_floods_7d or 0),
                "connector_errors_24h": int(row.connector_errors_24h or 0),
            }
            for row in result.all()
        }

        queue_result = await self.session.execute(
            select(ActionJob.account_id, func.count(ActionJob.id).label("queued_jobs"))
            .where(
                ActionJob.account_id.in_(account_ids),
                ActionJob.status.in_(ACTIVE_QUEUE_STATUSES),
            )
            .group_by(ActionJob.account_id)
        )
        for row in queue_result.all():
            metrics.setdefault(row.account_id, {})["queued_jobs"] = int(row.queued_jobs or 0)
        return metrics

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @classmethod
    def _aware_optional(cls, value: datetime | None) -> datetime | None:
        return cls._aware(value) if value is not None else None
