from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import ConnectorRegistry, connector_registry
from app.features.intelligence.models import AudienceMember, CommunityMembership
from app.features.inviter.models import InviteCampaign
from app.features.orchestration.models import ActionJob
from app.features.parser.models import ParsedChat


class OrchestrationService:
    """Plan platform actions in Postgres, then execute only due jobs."""

    def __init__(
        self,
        session: AsyncSession,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.session = session
        register_default_connectors()
        self.registry = registry or connector_registry

    async def plan_campaign(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        limit: int = 1_000,
        min_activity_score: float = 0.0,
        min_readiness_score: float = 0.0,
        account_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        campaign = await self._get_campaign(owner_id, campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")
        if campaign.status not in {"draft", "active", "paused"}:
            raise ValueError(f"Campaign cannot be planned from status: {campaign.status}")
        if campaign.source_type == "uploaded_list":
            raise ValueError("uploaded_list source is not connected to Audience Intelligence yet")

        platform = "telegram"
        connector = self.registry.get(platform)
        if not connector.capabilities.direct_invite:
            raise ValueError(f"Platform {platform} does not support direct_invite")

        accounts = await self._get_accounts(owner_id, account_ids)
        if not accounts:
            raise ValueError("No active accounts available for campaign")

        candidates = await self._get_candidates(
            owner_id=owner_id,
            campaign=campaign,
            platform=platform,
            min_activity_score=min_activity_score,
            min_readiness_score=min_readiness_score,
            limit=limit,
        )
        if not candidates:
            return {
                "campaign_id": campaign.id,
                "planned": 0,
                "candidates": 0,
                "accounts": len(accounts),
                "first_scheduled_at": None,
                "last_scheduled_at": None,
            }

        existing_result = await self.session.execute(
            select(ActionJob.audience_member_id).where(
                ActionJob.campaign_id == campaign.id,
                ActionJob.action == "direct_invite",
                ActionJob.status != "cancelled",
            )
        )
        already_planned = set(existing_result.scalars().all())
        candidates = [candidate for candidate in candidates if candidate.id not in already_planned]
        if not candidates:
            return {
                "campaign_id": campaign.id,
                "planned": 0,
                "candidates": 0,
                "accounts": len(accounts),
                "first_scheduled_at": None,
                "last_scheduled_at": None,
            }

        now = datetime.now(timezone.utc)
        future_result = await self.session.execute(
            select(ActionJob).where(
                ActionJob.account_id.in_([account.id for account in accounts]),
                ActionJob.status.in_(["planned", "dispatched", "processing", "retry_wait"]),
            )
        )
        existing_jobs = list(future_result.scalars().all())

        daily_counts: dict[tuple[UUID, object], int] = defaultdict(int)
        next_at: dict[UUID, datetime] = {account.id: now for account in accounts}
        sequence_counts: dict[UUID, int] = defaultdict(int)
        for job in existing_jobs:
            scheduled = self._aware(job.scheduled_at)
            daily_counts[(job.account_id, scheduled.date())] += 1
            sequence_counts[job.account_id] += 1
            if scheduled > next_at[job.account_id]:
                next_at[job.account_id] = scheduled

        account_limits = {
            account.id: self._effective_daily_limit(account, campaign, now)
            for account in accounts
        }
        rng = random.Random(f"{campaign.id}:{len(already_planned)}")
        account_by_id = {account.id: account for account in accounts}
        planned_jobs: list[ActionJob] = []

        for candidate in candidates:
            account_id = min(next_at, key=next_at.get)
            scheduled = self._next_available_time(
                account_id=account_id,
                desired_at=next_at[account_id],
                daily_limit=account_limits[account_id],
                daily_counts=daily_counts,
            )

            if sequence_counts[account_id] > 0 and sequence_counts[account_id] % campaign.pause_after_every == 0:
                scheduled += timedelta(
                    minutes=rng.uniform(campaign.pause_duration_min, campaign.pause_duration_max)
                )

            scheduled += timedelta(
                seconds=rng.uniform(campaign.invite_delay_min, campaign.invite_delay_max)
            )
            scheduled = self._next_available_time(
                account_id=account_id,
                desired_at=scheduled,
                daily_limit=account_limits[account_id],
                daily_counts=daily_counts,
            )

            job = ActionJob(
                owner_id=owner_id,
                campaign_id=campaign.id,
                account_id=account_id,
                audience_member_id=candidate.id,
                platform=platform,
                action="direct_invite",
                target_external_user_id=candidate.external_user_id,
                destination_external_id=str(campaign.target_chat_id),
                status="planned",
                scheduled_at=scheduled,
                max_attempts=3,
                payload={
                    "username": candidate.username,
                    "activity_score": candidate.activity_score,
                    "readiness_score": candidate.readiness_score,
                    "account_label": account_by_id[account_id].label,
                },
            )
            self.session.add(job)
            planned_jobs.append(job)
            daily_counts[(account_id, scheduled.date())] += 1
            sequence_counts[account_id] += 1
            next_at[account_id] = scheduled

        await self.session.commit()

        first_scheduled = min((job.scheduled_at for job in planned_jobs), default=None)
        last_scheduled = max((job.scheduled_at for job in planned_jobs), default=None)
        return {
            "campaign_id": campaign.id,
            "planned": len(planned_jobs),
            "candidates": len(candidates),
            "accounts": len(accounts),
            "first_scheduled_at": first_scheduled,
            "last_scheduled_at": last_scheduled,
        }

    async def start_campaign(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        limit: int = 1_000,
        min_activity_score: float = 0.0,
        min_readiness_score: float = 0.0,
        account_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        campaign = await self._get_campaign(owner_id, campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")
        if campaign.status not in {"draft", "paused", "active"}:
            raise ValueError(f"Campaign cannot be started from status: {campaign.status}")

        plan = await self.plan_campaign(
            owner_id=owner_id,
            campaign_id=campaign_id,
            limit=limit,
            min_activity_score=min_activity_score,
            min_readiness_score=min_readiness_score,
            account_ids=account_ids,
        )
        campaign.status = "active"
        if campaign.started_at is None:
            campaign.started_at = datetime.now(timezone.utc)
        await self.session.commit()
        return {**plan, "status": campaign.status}

    async def pause_campaign(self, *, owner_id: UUID, campaign_id: UUID) -> bool:
        campaign = await self._get_campaign(owner_id, campaign_id)
        if campaign is None:
            return False
        campaign.status = "paused"
        await self.session.commit()
        return True

    async def stop_campaign(self, *, owner_id: UUID, campaign_id: UUID) -> bool:
        campaign = await self._get_campaign(owner_id, campaign_id)
        if campaign is None:
            return False
        campaign.status = "completed"
        campaign.finished_at = datetime.now(timezone.utc)
        await self.session.execute(
            ActionJob.__table__.update()
            .where(
                ActionJob.campaign_id == campaign_id,
                ActionJob.status.in_(["planned", "dispatched", "retry_wait"]),
            )
            .values(status="cancelled", finished_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        return True

    async def list_jobs(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ActionJob], int]:
        clauses = [ActionJob.owner_id == owner_id]
        if campaign_id is not None:
            clauses.append(ActionJob.campaign_id == campaign_id)
        if status:
            clauses.append(ActionJob.status == status)

        total = (
            await self.session.execute(select(func.count(ActionJob.id)).where(*clauses))
        ).scalar() or 0
        result = await self.session.execute(
            select(ActionJob)
            .where(*clauses)
            .order_by(ActionJob.scheduled_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total)

    async def campaign_stats(self, *, owner_id: UUID, campaign_id: UUID) -> dict[str, Any]:
        campaign = await self._get_campaign(owner_id, campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")
        result = await self.session.execute(
            select(ActionJob.status, func.count(ActionJob.id))
            .where(ActionJob.campaign_id == campaign_id)
            .group_by(ActionJob.status)
        )
        by_status = {status: int(count) for status, count in result.all()}
        total = sum(by_status.values())
        success = by_status.get("success", 0)
        return {
            "campaign_id": campaign_id,
            "campaign_status": campaign.status,
            "total": total,
            "by_status": by_status,
            "success_rate": round(success / total * 100.0, 2) if total else 0.0,
        }

    async def claim_due_jobs(self, *, limit: int = 100) -> list[UUID]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ActionJob)
            .join(InviteCampaign, InviteCampaign.id == ActionJob.campaign_id)
            .where(
                InviteCampaign.status == "active",
                or_(
                    (ActionJob.status == "planned") & (ActionJob.scheduled_at <= now),
                    (ActionJob.status == "retry_wait") & (ActionJob.next_attempt_at <= now),
                ),
            )
            .order_by(ActionJob.scheduled_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        jobs = list(result.scalars().all())
        for job in jobs:
            job.status = "dispatched"
        await self.session.commit()
        return [job.id for job in jobs]

    async def execute_job(self, job_id: UUID) -> dict[str, Any]:
        result = await self.session.execute(select(ActionJob).where(ActionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return {"ok": False, "code": "JOB_NOT_FOUND"}
        if job.status in {"success", "failed", "cancelled"}:
            return {"ok": job.status == "success", "code": f"ALREADY_{job.status.upper()}"}

        campaign = await self._get_campaign(job.owner_id, job.campaign_id)
        if campaign is None or campaign.status not in {"active"}:
            job.status = "planned" if campaign and campaign.status == "paused" else "cancelled"
            await self.session.commit()
            return {"ok": False, "code": "CAMPAIGN_NOT_ACTIVE"}

        account_result = await self.session.execute(
            select(Account).where(
                Account.id == job.account_id,
                Account.owner_id == job.owner_id,
                Account.is_active.is_(True),
                Account.status == "active",
            )
        )
        account = account_result.scalar_one_or_none()
        if account is None:
            job.status = "failed"
            job.result_code = "ACCOUNT_UNAVAILABLE"
            job.result_message = "Assigned account is not active"
            job.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {"ok": False, "code": job.result_code}

        connector = self.registry.get(job.platform)
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        await self.session.commit()

        try:
            outcome = await connector.execute_action(
                job.action,
                account=account,
                target={"external_user_id": job.target_external_user_id},
                destination={"external_id": job.destination_external_id},
            )
        except Exception as exc:
            outcome = {
                "ok": False,
                "code": "CONNECTOR_ERROR",
                "retryable": True,
                "retry_after": min(60 * (2 ** max(job.attempts - 1, 0)), 3600),
                "message": str(exc),
            }

        now = datetime.now(timezone.utc)
        job.result_code = str(outcome.get("code") or "UNKNOWN")
        job.result_message = str(outcome.get("message") or "")[:2000] or None
        account.last_used_at = now

        if outcome.get("ok"):
            job.status = "success"
            job.finished_at = now
            job.next_attempt_at = None
            account.total_invites = (account.total_invites or 0) + 1
            account.daily_invite_count = (account.daily_invite_count or 0) + 1
        elif outcome.get("retryable") and job.attempts < job.max_attempts:
            retry_after = max(int(outcome.get("retry_after") or 60), 1)
            job.status = "retry_wait"
            job.next_attempt_at = now + timedelta(seconds=retry_after)
        else:
            job.status = "failed"
            job.finished_at = now
            job.next_attempt_at = None
            account.total_invite_errors = (account.total_invite_errors or 0) + 1

        attempts_total = (account.total_invites or 0) + (account.total_invite_errors or 0)
        account.success_rate = (account.total_invites or 0) / attempts_total if attempts_total else 0.0
        await self.session.commit()
        return {
            "ok": bool(outcome.get("ok")),
            "job_id": job.id,
            "status": job.status,
            "code": job.result_code,
            "next_attempt_at": job.next_attempt_at,
        }

    async def _get_campaign(self, owner_id: UUID, campaign_id: UUID) -> InviteCampaign | None:
        result = await self.session.execute(
            select(InviteCampaign).where(
                InviteCampaign.id == campaign_id,
                InviteCampaign.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_accounts(
        self,
        owner_id: UUID,
        account_ids: list[UUID] | None,
    ) -> list[Account]:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_ids:
            stmt = stmt.where(Account.id.in_(account_ids))
        result = await self.session.execute(stmt.order_by(Account.last_used_at.asc().nullsfirst()))
        return list(result.scalars().all())

    async def _get_candidates(
        self,
        *,
        owner_id: UUID,
        campaign: InviteCampaign,
        platform: str,
        min_activity_score: float,
        min_readiness_score: float,
        limit: int,
    ) -> list[AudienceMember]:
        stmt = select(AudienceMember).where(
            AudienceMember.owner_id == owner_id,
            AudienceMember.platform == platform,
            AudienceMember.is_bot.is_(False),
            AudienceMember.is_blacklisted.is_(False),
            func.coalesce(AudienceMember.activity_score, 0.0) >= min_activity_score,
            func.coalesce(AudienceMember.readiness_score, 0.0) >= min_readiness_score,
        )

        if campaign.source_type == "chat" and campaign.source_chat_id is not None:
            source_id = int(campaign.source_chat_id)
            chat_result = await self.session.execute(
                select(ParsedChat)
                .where(
                    ParsedChat.owner_id == owner_id,
                    ParsedChat.chat_id.in_({source_id, abs(source_id), -abs(source_id)}),
                )
                .limit(1)
            )
            source_chat = chat_result.scalar_one_or_none()
            if source_chat is None:
                raise ValueError("Source chat has not been analyzed in Discovery yet")
            stmt = stmt.join(
                CommunityMembership,
                CommunityMembership.audience_member_id == AudienceMember.id,
            ).where(CommunityMembership.parsed_chat_id == source_chat.id)

        stmt = stmt.order_by(
            AudienceMember.readiness_score.desc().nullslast(),
            AudienceMember.activity_score.desc().nullslast(),
            AudienceMember.last_activity_at.desc().nullslast(),
        ).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @classmethod
    def _effective_daily_limit(
        cls,
        account: Account,
        campaign: InviteCampaign,
        now: datetime,
    ) -> int:
        daily_limit = max(int(campaign.daily_limit_per_account), 1)
        if campaign.warmup_enabled and account.created_at:
            created_at = cls._aware(account.created_at)
            account_age_days = max((now - created_at).days, 0)
            if account_age_days < campaign.warmup_days:
                daily_limit = max(int(daily_limit * campaign.warmup_limit_factor), 1)
        return daily_limit

    @staticmethod
    def _next_available_time(
        *,
        account_id: UUID,
        desired_at: datetime,
        daily_limit: int,
        daily_counts: dict[tuple[UUID, object], int],
    ) -> datetime:
        candidate = desired_at
        while daily_counts[(account_id, candidate.date())] >= daily_limit:
            candidate += timedelta(days=1)
        return candidate
