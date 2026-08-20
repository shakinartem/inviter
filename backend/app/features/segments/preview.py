from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import fmean
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.segments.preview_schemas import SegmentPreviewRequest
from app.features.segments.service import SegmentService


class SegmentPreviewService:
    """Evaluate a segment definition without persisting or materializing it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.segment_service = SegmentService(session)

    async def preview(self, owner_id: UUID, payload: SegmentPreviewRequest) -> dict[str, Any]:
        platform = payload.platform.strip().lower()
        criteria = payload.criteria
        await self.segment_service._validate_criteria_scope(owner_id, criteria)
        now = datetime.now(timezone.utc)
        candidates = await self.segment_service._match_candidates(
            owner_id=owner_id,
            platform=platform,
            criteria=criteria,
            now=now,
        )
        strongest = await self.segment_service._strongest_signals(
            member_ids=[member.id for member in candidates],
            lookback_days=criteria.signal_lookback_days,
            now=now,
        )

        warnings: list[str] = []
        if not criteria.community_ids:
            warnings.append("global_scope")
        if len(candidates) >= criteria.max_members:
            warnings.append("max_members_reached")
        if len(candidates) < 25:
            warnings.append("small_cohort")

        distribution = Counter(strongest.get(member.id) or "no_intent_signal" for member in candidates)
        sample = []
        for member in candidates[:20]:
            sample.append(
                {
                    "audience_member_id": member.id,
                    "username": member.username,
                    "first_name": member.first_name,
                    "last_name": member.last_name,
                    "activity_score": member.activity_score,
                    "relevance_score": member.relevance_score,
                    "intent_score": member.intent_score,
                    "readiness_score": member.readiness_score,
                    "strongest_signal_type": strongest.get(member.id),
                }
            )

        return {
            "platform": platform,
            "matched_count": len(candidates),
            "max_members": criteria.max_members,
            "average_activity_score": self._average(member.activity_score for member in candidates),
            "average_relevance_score": self._average(member.relevance_score for member in candidates),
            "average_intent_score": self._average(member.intent_score for member in candidates),
            "average_readiness_score": self._average(member.readiness_score for member in candidates),
            "strongest_signal_distribution": dict(distribution.most_common()),
            "community_count": len(criteria.community_ids),
            "warnings": warnings,
            "sample": sample,
        }

    @staticmethod
    def _average(values) -> float | None:
        filtered = [float(value) for value in values if value is not None]
        if not filtered:
            return None
        return round(fmean(filtered), 2)
