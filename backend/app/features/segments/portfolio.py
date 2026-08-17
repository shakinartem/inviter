from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.learning.models import ActionFeatureSnapshot
from app.features.segments.forecast import SegmentYieldForecastService
from app.features.segments.models import AudienceSegment


class CachedYieldForecastService(SegmentYieldForecastService):
    """Request-local cache so a portfolio reads mature history only once per context."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._history_cache: dict[tuple[Any, ...], tuple[list[ActionFeatureSnapshot], bool]] = {}
        self._positive_cache: dict[tuple[Any, ...], set[UUID]] = {}

    async def _mature_history(
        self,
        *,
        owner_id: UUID,
        platform: str,
        horizon_hours: int,
    ) -> tuple[list[ActionFeatureSnapshot], bool]:
        key = (owner_id, platform, horizon_hours)
        if key not in self._history_cache:
            self._history_cache[key] = await super()._mature_history(
                owner_id=owner_id,
                platform=platform,
                horizon_hours=horizon_hours,
            )
        return self._history_cache[key]

    async def _positive_jobs(
        self,
        *,
        history: list[ActionFeatureSnapshot],
        owner_id: UUID,
        stage: str,
        event_type: str,
        horizon_hours: int,
        min_confidence: float,
    ) -> set[UUID]:
        history_token = (
            len(history),
            str(history[0].id) if history else "empty",
            str(history[-1].id) if history else "empty",
        )
        key = (
            owner_id,
            stage,
            event_type,
            horizon_hours,
            round(min_confidence, 6),
            history_token,
        )
        if key not in self._positive_cache:
            self._positive_cache[key] = await super()._positive_jobs(
                history=history,
                owner_id=owner_id,
                stage=stage,
                event_type=event_type,
                horizon_hours=horizon_hours,
                min_confidence=min_confidence,
            )
        return self._positive_cache[key]


class OpportunityPortfolioService:
    """Rank materialized Opportunities at a common action budget."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def forecast_portfolio(
        self,
        *,
        owner_id: UUID,
        stage: str = "business",
        event_type: str = "converted",
        horizon_hours: int = 168,
        action_budget: int = 1_000,
        platform: str | None = None,
        limit_segments: int = 20,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        if limit_segments < 1 or limit_segments > 50:
            raise ValueError("limit_segments must be between 1 and 50")

        clauses = [
            AudienceSegment.owner_id == owner_id,
            AudienceSegment.is_active.is_(True),
            AudienceSegment.last_refreshed_at.is_not(None),
            AudienceSegment.matched_count > 0,
        ]
        if platform:
            clauses.append(AudienceSegment.platform == platform.strip().lower())

        result = await self.session.execute(
            select(AudienceSegment)
            .where(*clauses)
            .order_by(
                AudienceSegment.matched_count.desc(),
                AudienceSegment.updated_at.desc(),
            )
            .limit(limit_segments)
        )
        segments = list(result.scalars().all())
        forecast_service = CachedYieldForecastService(self.session)
        rows: list[dict[str, Any]] = []

        for segment in segments:
            forecast = await forecast_service.forecast(
                owner_id=owner_id,
                segment_id=segment.id,
                stage=stage,
                event_type=event_type,
                horizon_hours=horizon_hours,
                budget=action_budget,
                min_confidence=min_confidence,
            )
            contextual_coverage = 100.0 - float(
                forecast.get("evidence_coverage", {}).get("global", 100.0)
            )
            conservative = float(forecast["confidence_low_outcomes"])
            # Ranking remains deliberately conservative. A quality multiplier
            # prevents a noisy tiny cohort from beating a well-supported one on
            # an unstable lower bound alone.
            quality_multiplier = {
                "ready": 1.0,
                "limited": 0.75,
                "insufficient": 0.0,
            }[forecast["quality_status"]]
            score = conservative * quality_multiplier
            rows.append(
                {
                    "segment_id": segment.id,
                    "segment_name": segment.name,
                    "matched_count": segment.matched_count,
                    "evaluated_members": forecast["evaluated_members"],
                    "expected_outcomes": forecast["expected_outcomes"],
                    "conservative_outcomes": conservative,
                    "upside_outcomes": forecast["confidence_high_outcomes"],
                    "expected_rate": forecast["expected_rate"],
                    "conservative_rate": forecast["confidence_low_rate"],
                    "quality_status": forecast["quality_status"],
                    "frozen_history_ratio": forecast["frozen_history_ratio"],
                    "contextual_coverage": round(contextual_coverage, 2),
                    "score": round(score, 4),
                    "warnings": forecast["warnings"],
                }
            )

        rows.sort(
            key=lambda row: (
                row["score"],
                row["conservative_outcomes"],
                row["expected_outcomes"],
            ),
            reverse=True,
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index

        recommendation = next(
            (
                row
                for row in rows
                if row["quality_status"] == "ready"
                and row["conservative_outcomes"] > 0
                and row["contextual_coverage"] >= 70.0
            ),
            None,
        )

        warnings = ["observational_not_causal", "audience_overlap_not_deduplicated"]
        if rows and recommendation is None:
            warnings.append("no_high_confidence_recommendation")
        if not rows:
            warnings.append("no_materialized_opportunities")

        return {
            "stage": stage.strip().lower(),
            "event_type": event_type.strip().lower().replace(" ", "_"),
            "horizon_hours": horizon_hours,
            "action_budget": action_budget,
            "ranking_basis": "quality_adjusted_conservative_expected_outcomes",
            "recommendation_segment_id": recommendation["segment_id"] if recommendation else None,
            "recommendation_name": recommendation["segment_name"] if recommendation else None,
            "warnings": warnings,
            "rows": rows,
        }
