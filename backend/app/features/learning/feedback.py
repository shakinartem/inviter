from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.intelligence.models import AudienceMember
from app.features.inviter.models import InviteCampaign
from app.features.learning.models import ActionFeatureSnapshot, OutcomeEvent
from app.features.orchestration.models import ActionJob


class FeedbackQueueService:
    """Operator-facing queue of executed actions that can receive outcome labels."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_actions(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses = [
            ActionJob.owner_id == owner_id,
            ActionJob.attempts > 0,
        ]
        if campaign_id is not None:
            clauses.append(ActionJob.campaign_id == campaign_id)

        total_result = await self.session.execute(
            select(func.count(ActionJob.id)).where(*clauses)
        )
        total = int(total_result.scalar() or 0)

        result = await self.session.execute(
            select(ActionJob, AudienceMember, InviteCampaign, ActionFeatureSnapshot)
            .join(AudienceMember, AudienceMember.id == ActionJob.audience_member_id)
            .join(InviteCampaign, InviteCampaign.id == ActionJob.campaign_id)
            .outerjoin(ActionFeatureSnapshot, ActionFeatureSnapshot.action_job_id == ActionJob.id)
            .where(*clauses)
            .order_by(
                ActionJob.finished_at.desc().nullslast(),
                ActionJob.started_at.desc().nullslast(),
            )
            .offset(skip)
            .limit(limit)
        )
        rows = list(result.all())
        job_ids = [job.id for job, _member, _campaign, _snapshot in rows]

        outcomes_by_job: dict[UUID, list[OutcomeEvent]] = defaultdict(list)
        if job_ids:
            outcomes_result = await self.session.execute(
                select(OutcomeEvent)
                .where(
                    OutcomeEvent.owner_id == owner_id,
                    OutcomeEvent.action_job_id.in_(job_ids),
                )
                .order_by(OutcomeEvent.observed_at.asc())
            )
            for event in outcomes_result.scalars().all():
                if event.action_job_id is not None:
                    outcomes_by_job[event.action_job_id].append(event)

        items: list[dict[str, Any]] = []
        for job, member, campaign, snapshot in rows:
            display_name = " ".join(
                part for part in [member.first_name, member.last_name] if part
            ).strip()
            display_name = display_name or member.username or member.external_user_id
            items.append(
                {
                    "action_job_id": job.id,
                    "campaign_id": campaign.id,
                    "campaign_title": campaign.title,
                    "audience_member_id": member.id,
                    "person": display_name,
                    "username": member.username,
                    "platform": job.platform,
                    "action": job.action,
                    "job_status": job.status,
                    "result_code": job.result_code,
                    "attempts": job.attempts,
                    "executed_at": job.finished_at or job.started_at,
                    "activity_score": snapshot.activity_score if snapshot else None,
                    "intent_score": snapshot.intent_score if snapshot else None,
                    "readiness_score": snapshot.readiness_score if snapshot else None,
                    "strongest_signal_type": snapshot.strongest_signal_type if snapshot else None,
                    "outcomes": [
                        {
                            "stage": event.stage,
                            "event_type": event.event_type,
                            "success": event.success,
                            "source": event.source,
                            "observed_at": event.observed_at,
                        }
                        for event in outcomes_by_job.get(job.id, [])
                    ],
                }
            )
        return items, total
