from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.intelligence.models import IntentSignal
from app.features.learning.models import ActionFeatureSnapshot
from app.features.orchestration.models import ActionJob
from app.features.segments.models import CampaignAudienceMember, CampaignAudienceSource


FROZEN_SNAPSHOT_VERSION = "action-feature-v2-frozen-cohort"


class FrozenDecisionSnapshotService:
    """Persist the features the planner actually knew when the cohort was frozen."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_for_jobs(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        jobs: list[ActionJob],
    ) -> int:
        if not jobs:
            return 0
        source_result = await self.session.execute(
            select(CampaignAudienceSource).where(
                CampaignAudienceSource.owner_id == owner_id,
                CampaignAudienceSource.campaign_id == campaign_id,
            )
        )
        source = source_result.scalar_one_or_none()
        if source is None:
            return 0

        eligible_jobs = [job for job in jobs if job.status != "cancelled"]
        if not eligible_jobs:
            return 0
        job_ids = [job.id for job in eligible_jobs]
        existing_result = await self.session.execute(
            select(ActionFeatureSnapshot.action_job_id).where(
                ActionFeatureSnapshot.action_job_id.in_(job_ids)
            )
        )
        existing = set(existing_result.scalars().all())
        pending_jobs = [job for job in eligible_jobs if job.id not in existing]
        if not pending_jobs:
            return 0

        member_ids = [job.audience_member_id for job in pending_jobs]
        frozen_result = await self.session.execute(
            select(CampaignAudienceMember).where(
                CampaignAudienceMember.campaign_source_id == source.id,
                CampaignAudienceMember.audience_member_id.in_(member_ids),
            )
        )
        frozen_by_member = {
            item.audience_member_id: item for item in frozen_result.scalars().all()
        }

        # Only signals that existed by cohort freeze are allowed into model-version
        # metadata. This prevents later enrichment from leaking into history.
        signals_result = await self.session.execute(
            select(IntentSignal)
            .where(
                IntentSignal.audience_member_id.in_(member_ids),
                IntentSignal.observed_at <= source.frozen_at,
            )
            .order_by(IntentSignal.audience_member_id, IntentSignal.observed_at.desc())
        )
        signals_by_member: dict[UUID, list[IntentSignal]] = defaultdict(list)
        for signal in signals_result.scalars().all():
            signals_by_member[signal.audience_member_id].append(signal)

        created = 0
        for job in pending_jobs:
            frozen = frozen_by_member.get(job.audience_member_id)
            if frozen is None:
                continue
            signals = signals_by_member.get(job.audience_member_id, [])
            type_counts = Counter(signal.signal_type for signal in signals[:100])
            model_versions = sorted({signal.model_version for signal in signals[:100]})
            latest_signal = signals[0].observed_at if signals else None
            scheduled_at = job.scheduled_at
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

            self.session.add(
                ActionFeatureSnapshot(
                    owner_id=job.owner_id,
                    action_job_id=job.id,
                    campaign_id=job.campaign_id,
                    audience_member_id=job.audience_member_id,
                    platform=job.platform,
                    action=job.action,
                    captured_at=source.frozen_at,
                    first_transport_at=None,
                    activity_score=frozen.activity_score,
                    relevance_score=frozen.relevance_score,
                    quality_score=None,
                    intent_score=frozen.intent_score,
                    readiness_score=frozen.readiness_score,
                    signal_count=len(signals),
                    strongest_signal_type=frozen.strongest_signal_type,
                    intent_model_versions=model_versions or None,
                    feature_payload={
                        "decision_source": "frozen_campaign_cohort",
                        "campaign_source_id": str(source.id),
                        "segment_id": str(source.segment_id),
                        "segment_refresh_sequence": source.segment_refresh_sequence,
                        "criteria_snapshot": source.criteria_snapshot,
                        "match_reasons": frozen.match_reasons,
                        "recent_signal_type_counts": dict(type_counts),
                        "latest_signal_at": latest_signal.isoformat() if latest_signal else None,
                        "scheduled_hour_utc": scheduled_at.hour,
                        "scheduled_weekday_utc": scheduled_at.weekday(),
                        "max_attempts": job.max_attempts,
                    },
                    snapshot_version=FROZEN_SNAPSHOT_VERSION,
                )
            )
            created += 1
        await self.session.flush()
        return created
