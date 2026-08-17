from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.features.accounts.models import Account
from app.features.intelligence.models import AudienceMember
from app.features.inviter.models import InviteCampaign
from app.features.learning.service import OutcomeLearningService
from app.features.orchestration.destinations import CampaignDestinationService
from app.features.orchestration.models import ActionJob
from app.features.orchestration.service import OrchestrationService
from app.features.segments.models import CampaignAudienceMember, CampaignAudienceSource


class ConnectionAwareOrchestrationService(OrchestrationService):
    """Bind actions to compatible connections, frozen cohorts, stable refs and labels."""

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
        destination = await CampaignDestinationService(self.session).get_for_campaign(
            owner_id=owner_id,
            campaign_id=campaign_id,
        )
        if destination is None:
            raise ValueError(
                "Campaign has no canonical destination. Sync the destination community and recreate the campaign."
            )
        if destination.platform != "telegram":
            raise ValueError(
                f"direct_invite is not enabled for destination platform: {destination.platform}"
            )

        result = await super().plan_campaign(
            owner_id=owner_id,
            campaign_id=campaign_id,
            limit=limit,
            min_activity_score=min_activity_score,
            min_readiness_score=min_readiness_score,
            account_ids=account_ids,
        )

        jobs_result = await self.session.execute(
            select(ActionJob).where(
                ActionJob.campaign_id == campaign_id,
                ActionJob.action == "direct_invite",
                ActionJob.status.in_(["planned", "retry_wait"]),
            )
        )
        jobs = list(jobs_result.scalars().all())
        if jobs:
            member_ids = {job.audience_member_id for job in jobs}
            members_result = await self.session.execute(
                select(AudienceMember).where(AudienceMember.id.in_(member_ids))
            )
            members = {member.id: member for member in members_result.scalars().all()}

            for job in jobs:
                member = members.get(job.audience_member_id)
                if member is None or not self._is_resolvable_telegram_member(member):
                    job.status = "cancelled"
                    job.result_code = "UNRESOLVABLE_TARGET"
                    job.result_message = "Telegram target has neither username nor access_hash"
                    continue
                job.target_external_user_id = self._telegram_member_ref(member)
                job.destination_external_id = destination.connector_ref

            await self.session.commit()

        return result

    async def execute_job(self, job_id: UUID) -> dict[str, Any]:
        """Execute through the base engine while preserving unbiased learning data."""
        job_result = await self.session.execute(select(ActionJob).where(ActionJob.id == job_id))
        job = job_result.scalar_one_or_none()
        learning = OutcomeLearningService(self.session)

        if (
            job is not None
            and job.status not in {"success", "failed", "cancelled"}
            and job.attempts == 0
        ):
            await learning.ensure_action_snapshot(job.id)

        result = await super().execute_job(job_id)
        code = str(result.get("code") or "")
        if job is not None and not code.startswith("ALREADY_"):
            await learning.record_transport_result(job.id, result)
        return result

    async def _get_accounts(
        self,
        owner_id: UUID,
        account_ids: list[UUID] | None,
    ) -> list[Account]:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.platform == "telegram",
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_ids:
            stmt = stmt.where(Account.id.in_(account_ids))
        result = await self.session.execute(
            stmt.order_by(
                Account.health_score.desc(),
                Account.last_used_at.asc().nullsfirst(),
            )
        )
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
        source_result = await self.session.execute(
            select(CampaignAudienceSource).where(
                CampaignAudienceSource.owner_id == owner_id,
                CampaignAudienceSource.campaign_id == campaign.id,
            )
        )
        source = source_result.scalar_one_or_none()

        if source is not None:
            # Use scores frozen with the campaign cohort, not mutable profile
            # scores. This keeps planning reproducible even after later enrichment.
            stmt = (
                select(AudienceMember)
                .join(
                    CampaignAudienceMember,
                    CampaignAudienceMember.audience_member_id == AudienceMember.id,
                )
                .where(
                    CampaignAudienceMember.campaign_source_id == source.id,
                    AudienceMember.owner_id == owner_id,
                    AudienceMember.platform == platform,
                    AudienceMember.is_blacklisted.is_(False),
                    CampaignAudienceMember.activity_score >= min_activity_score,
                    CampaignAudienceMember.readiness_score >= min_readiness_score,
                )
                .order_by(
                    CampaignAudienceMember.readiness_score.desc().nullslast(),
                    CampaignAudienceMember.intent_score.desc().nullslast(),
                    CampaignAudienceMember.activity_score.desc().nullslast(),
                )
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            candidates = list(result.scalars().all())
        else:
            # Legacy campaigns created before Opportunity Segments continue to work.
            candidates = await super()._get_candidates(
                owner_id=owner_id,
                campaign=campaign,
                platform=platform,
                min_activity_score=min_activity_score,
                min_readiness_score=min_readiness_score,
                limit=limit,
            )

        if platform != "telegram":
            return candidates
        return [candidate for candidate in candidates if self._is_resolvable_telegram_member(candidate)]

    @staticmethod
    def _is_resolvable_telegram_member(member: AudienceMember) -> bool:
        if member.username:
            return True
        platform_data = member.platform_data or {}
        return bool(platform_data.get("access_hash"))

    @staticmethod
    def _telegram_member_ref(member: AudienceMember) -> str:
        if member.username:
            return member.username if member.username.startswith("@") else f"@{member.username}"
        access_hash = (member.platform_data or {}).get("access_hash")
        if not access_hash:
            raise ValueError("Telegram audience member is not resolvable")
        return f"user:{member.external_user_id}:{access_hash}"
