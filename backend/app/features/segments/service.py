from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.intelligence.models import AudienceMember, CommunityMembership, IntentSignal
from app.features.parser.models import ParsedChat
from app.features.segments.models import (
    AudienceSegment,
    AudienceSegmentMember,
    CampaignAudienceMember,
    CampaignAudienceSource,
)
from app.features.segments.schemas import SegmentCreate, SegmentCriteria, SegmentUpdate


class SegmentService:
    """Create reusable intent/readiness cohorts and freeze them for campaigns."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, owner_id: UUID, payload: SegmentCreate) -> AudienceSegment:
        name = payload.name.strip()
        existing = await self.session.execute(
            select(AudienceSegment.id).where(
                AudienceSegment.owner_id == owner_id,
                func.lower(AudienceSegment.name) == name.lower(),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("A segment with this name already exists")

        platform = payload.platform.strip().lower()
        await self._validate_criteria_scope(owner_id, payload.criteria)
        segment = AudienceSegment(
            owner_id=owner_id,
            name=name,
            description=payload.description,
            platform=platform,
            criteria=payload.criteria.model_dump(mode="json"),
            criteria_version="segment-v1",
            is_active=True,
            matched_count=0,
            refresh_count=0,
        )
        self.session.add(segment)
        await self.session.commit()
        await self.session.refresh(segment)
        return segment

    async def list(
        self,
        owner_id: UUID,
        *,
        active_only: bool | None = None,
        platform: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AudienceSegment], int]:
        clauses = [AudienceSegment.owner_id == owner_id]
        if active_only is not None:
            clauses.append(AudienceSegment.is_active == active_only)
        if platform:
            clauses.append(AudienceSegment.platform == platform.strip().lower())

        total_result = await self.session.execute(
            select(func.count(AudienceSegment.id)).where(*clauses)
        )
        total = int(total_result.scalar() or 0)
        result = await self.session.execute(
            select(AudienceSegment)
            .where(*clauses)
            .order_by(
                AudienceSegment.is_active.desc(),
                AudienceSegment.updated_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get(self, owner_id: UUID, segment_id: UUID) -> AudienceSegment | None:
        result = await self.session.execute(
            select(AudienceSegment).where(
                AudienceSegment.id == segment_id,
                AudienceSegment.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        owner_id: UUID,
        segment_id: UUID,
        payload: SegmentUpdate,
    ) -> AudienceSegment | None:
        segment = await self.get(owner_id, segment_id)
        if segment is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            name = str(updates["name"]).strip()
            duplicate = await self.session.execute(
                select(AudienceSegment.id).where(
                    AudienceSegment.owner_id == owner_id,
                    AudienceSegment.id != segment_id,
                    func.lower(AudienceSegment.name) == name.lower(),
                )
            )
            if duplicate.scalar_one_or_none() is not None:
                raise ValueError("A segment with this name already exists")
            segment.name = name
        if "description" in updates:
            segment.description = updates["description"]
        if "is_active" in updates:
            segment.is_active = bool(updates["is_active"])
        if payload.criteria is not None:
            await self._validate_criteria_scope(owner_id, payload.criteria)
            segment.criteria = payload.criteria.model_dump(mode="json")
            segment.matched_count = 0
            segment.last_refreshed_at = None
            await self.session.execute(
                delete(AudienceSegmentMember).where(AudienceSegmentMember.segment_id == segment.id)
            )

        await self.session.commit()
        await self.session.refresh(segment)
        return segment

    async def refresh(self, owner_id: UUID, segment_id: UUID) -> dict[str, Any]:
        segment = await self.get(owner_id, segment_id)
        if segment is None:
            raise ValueError("Segment not found")
        if not segment.is_active:
            raise ValueError("Inactive segment cannot be refreshed")

        criteria = SegmentCriteria.model_validate(segment.criteria)
        await self._validate_criteria_scope(owner_id, criteria)
        now = datetime.now(timezone.utc)
        candidates = await self._match_candidates(
            owner_id=owner_id,
            platform=segment.platform,
            criteria=criteria,
            now=now,
        )
        strongest_signals = await self._strongest_signals(
            member_ids=[member.id for member in candidates],
            lookback_days=criteria.signal_lookback_days,
            now=now,
        )

        await self.session.execute(
            delete(AudienceSegmentMember).where(AudienceSegmentMember.segment_id == segment.id)
        )
        refresh_sequence = (segment.refresh_count or 0) + 1
        for member in candidates:
            strongest_signal_type = strongest_signals.get(member.id)
            self.session.add(
                AudienceSegmentMember(
                    segment_id=segment.id,
                    audience_member_id=member.id,
                    matched_at=now,
                    activity_score=member.activity_score,
                    relevance_score=member.relevance_score,
                    intent_score=member.intent_score,
                    readiness_score=member.readiness_score,
                    strongest_signal_type=strongest_signal_type,
                    match_reasons=self._match_reasons(member, criteria, strongest_signal_type),
                    refresh_sequence=refresh_sequence,
                )
            )

        segment.matched_count = len(candidates)
        segment.last_refreshed_at = now
        segment.refresh_count = refresh_sequence
        await self.session.commit()
        return {
            "segment_id": segment.id,
            "matched_count": len(candidates),
            "refresh_sequence": refresh_sequence,
            "refreshed_at": now,
        }

    async def list_members(
        self,
        owner_id: UUID,
        segment_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        segment = await self.get(owner_id, segment_id)
        if segment is None:
            raise ValueError("Segment not found")

        total_result = await self.session.execute(
            select(func.count(AudienceSegmentMember.id)).where(
                AudienceSegmentMember.segment_id == segment.id
            )
        )
        total = int(total_result.scalar() or 0)
        result = await self.session.execute(
            select(AudienceSegmentMember, AudienceMember)
            .join(AudienceMember, AudienceMember.id == AudienceSegmentMember.audience_member_id)
            .where(AudienceSegmentMember.segment_id == segment.id)
            .order_by(
                AudienceSegmentMember.readiness_score.desc().nullslast(),
                AudienceSegmentMember.intent_score.desc().nullslast(),
                AudienceSegmentMember.activity_score.desc().nullslast(),
            )
            .offset(skip)
            .limit(limit)
        )
        items: list[dict[str, Any]] = []
        for membership, member in result.all():
            items.append(
                {
                    "segment_member_id": membership.id,
                    "audience_member_id": member.id,
                    "platform": member.platform,
                    "username": member.username,
                    "first_name": member.first_name,
                    "last_name": member.last_name,
                    "activity_score": membership.activity_score,
                    "relevance_score": membership.relevance_score,
                    "intent_score": membership.intent_score,
                    "readiness_score": membership.readiness_score,
                    "strongest_signal_type": membership.strongest_signal_type,
                    "matched_at": membership.matched_at,
                    "match_reasons": membership.match_reasons,
                }
            )
        return items, total

    async def freeze_for_campaign(
        self,
        *,
        owner_id: UUID,
        segment_id: UUID,
        campaign_id: UUID,
    ) -> CampaignAudienceSource:
        segment = await self.get(owner_id, segment_id)
        if segment is None:
            raise ValueError("Audience segment not found")
        if not segment.is_active:
            raise ValueError("Audience segment is inactive")
        if segment.last_refreshed_at is None:
            raise ValueError("Audience segment must be refreshed before campaign creation")
        if segment.matched_count <= 0:
            raise ValueError("Audience segment has no matching members")

        existing = await self.session.execute(
            select(CampaignAudienceSource).where(CampaignAudienceSource.campaign_id == campaign_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Campaign already has a frozen audience source")

        memberships_result = await self.session.execute(
            select(AudienceSegmentMember)
            .where(AudienceSegmentMember.segment_id == segment.id)
            .order_by(AudienceSegmentMember.readiness_score.desc().nullslast())
        )
        memberships = list(memberships_result.scalars().all())
        if not memberships:
            raise ValueError("Audience segment has no materialized members")

        now = datetime.now(timezone.utc)
        source = CampaignAudienceSource(
            owner_id=owner_id,
            campaign_id=campaign_id,
            segment_id=segment.id,
            frozen_at=now,
            member_count=len(memberships),
            criteria_snapshot=dict(segment.criteria),
            segment_refresh_sequence=segment.refresh_count,
        )
        self.session.add(source)
        await self.session.flush()

        for membership in memberships:
            self.session.add(
                CampaignAudienceMember(
                    campaign_source_id=source.id,
                    audience_member_id=membership.audience_member_id,
                    activity_score=membership.activity_score,
                    relevance_score=membership.relevance_score,
                    intent_score=membership.intent_score,
                    readiness_score=membership.readiness_score,
                    strongest_signal_type=membership.strongest_signal_type,
                    match_reasons=membership.match_reasons,
                )
            )

        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def campaign_source(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
    ) -> CampaignAudienceSource | None:
        result = await self.session.execute(
            select(CampaignAudienceSource).where(
                CampaignAudienceSource.owner_id == owner_id,
                CampaignAudienceSource.campaign_id == campaign_id,
            )
        )
        return result.scalar_one_or_none()

    async def frozen_member_ids(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
    ) -> list[UUID] | None:
        source = await self.campaign_source(owner_id=owner_id, campaign_id=campaign_id)
        if source is None:
            return None
        result = await self.session.execute(
            select(CampaignAudienceMember.audience_member_id).where(
                CampaignAudienceMember.campaign_source_id == source.id
            )
        )
        return list(result.scalars().all())

    async def _match_candidates(
        self,
        *,
        owner_id: UUID,
        platform: str,
        criteria: SegmentCriteria,
        now: datetime,
    ) -> list[AudienceMember]:
        clauses = [
            AudienceMember.owner_id == owner_id,
            AudienceMember.platform == platform,
            AudienceMember.is_blacklisted.is_(False),
        ]
        if not criteria.include_bots:
            clauses.append(AudienceMember.is_bot.is_(False))
        if criteria.min_activity_score is not None:
            clauses.append(AudienceMember.activity_score >= criteria.min_activity_score)
        if criteria.min_relevance_score is not None:
            clauses.append(AudienceMember.relevance_score >= criteria.min_relevance_score)
        if criteria.min_quality_score is not None:
            clauses.append(AudienceMember.quality_score >= criteria.min_quality_score)
        if criteria.min_intent_score is not None:
            clauses.append(AudienceMember.intent_score >= criteria.min_intent_score)
        if criteria.min_readiness_score is not None:
            clauses.append(AudienceMember.readiness_score >= criteria.min_readiness_score)
        if criteria.last_activity_days is not None:
            clauses.append(
                AudienceMember.last_activity_at >= now - timedelta(days=criteria.last_activity_days)
            )
        if criteria.community_ids:
            clauses.append(
                exists(
                    select(CommunityMembership.id).where(
                        CommunityMembership.audience_member_id == AudienceMember.id,
                        CommunityMembership.parsed_chat_id.in_(criteria.community_ids),
                    )
                )
            )
        if criteria.signal_types:
            signal_cutoff = now - timedelta(days=criteria.signal_lookback_days)
            clauses.append(
                exists(
                    select(IntentSignal.id).where(
                        IntentSignal.audience_member_id == AudienceMember.id,
                        IntentSignal.signal_type.in_(criteria.signal_types),
                        IntentSignal.observed_at >= signal_cutoff,
                    )
                )
            )
        if criteria.min_communities is not None:
            membership_count = (
                select(func.count(CommunityMembership.id))
                .where(CommunityMembership.audience_member_id == AudienceMember.id)
                .correlate(AudienceMember)
                .scalar_subquery()
            )
            clauses.append(membership_count >= criteria.min_communities)

        if criteria.sort_by == "intent":
            ordering = (
                AudienceMember.intent_score.desc().nullslast(),
                AudienceMember.readiness_score.desc().nullslast(),
                AudienceMember.activity_score.desc().nullslast(),
            )
        elif criteria.sort_by == "activity":
            ordering = (
                AudienceMember.activity_score.desc().nullslast(),
                AudienceMember.readiness_score.desc().nullslast(),
                AudienceMember.intent_score.desc().nullslast(),
            )
        else:
            ordering = (
                AudienceMember.readiness_score.desc().nullslast(),
                AudienceMember.intent_score.desc().nullslast(),
                AudienceMember.activity_score.desc().nullslast(),
            )

        result = await self.session.execute(
            select(AudienceMember)
            .where(*clauses)
            .order_by(*ordering)
            .limit(criteria.max_members)
        )
        return list(result.scalars().all())

    async def _strongest_signals(
        self,
        *,
        member_ids: list[UUID],
        lookback_days: int,
        now: datetime,
    ) -> dict[UUID, str]:
        if not member_ids:
            return {}
        cutoff = now - timedelta(days=lookback_days)
        rank = func.row_number().over(
            partition_by=IntentSignal.audience_member_id,
            order_by=(IntentSignal.score * IntentSignal.confidence).desc(),
        ).label("signal_rank")
        ranked = (
            select(
                IntentSignal.audience_member_id.label("member_id"),
                IntentSignal.signal_type.label("signal_type"),
                rank,
            )
            .where(
                IntentSignal.audience_member_id.in_(member_ids),
                IntentSignal.observed_at >= cutoff,
            )
            .subquery()
        )
        result = await self.session.execute(
            select(ranked.c.member_id, ranked.c.signal_type).where(ranked.c.signal_rank == 1)
        )
        return {member_id: signal_type for member_id, signal_type in result.all()}

    async def _validate_criteria_scope(self, owner_id: UUID, criteria: SegmentCriteria) -> None:
        if not criteria.community_ids:
            return
        result = await self.session.execute(
            select(ParsedChat.id).where(
                ParsedChat.owner_id == owner_id,
                ParsedChat.id.in_(criteria.community_ids),
            )
        )
        found = set(result.scalars().all())
        missing = set(criteria.community_ids) - found
        if missing:
            raise ValueError("One or more segment communities are not available to this user")

    @staticmethod
    def _match_reasons(
        member: AudienceMember,
        criteria: SegmentCriteria,
        strongest_signal_type: str | None,
    ) -> dict[str, Any]:
        return {
            "criteria": criteria.model_dump(mode="json"),
            "observed": {
                "activity_score": member.activity_score,
                "relevance_score": member.relevance_score,
                "quality_score": member.quality_score,
                "intent_score": member.intent_score,
                "readiness_score": member.readiness_score,
                "last_activity_at": (
                    member.last_activity_at.isoformat() if member.last_activity_at else None
                ),
                "strongest_signal_type": strongest_signal_type,
            },
        }
