from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(slots=True)
class CommunityScoreInput:
    participants_count: int | None = None
    active_1d: int | None = None
    active_7d: int | None = None
    messages_1d: int | None = None
    messages_7d: int | None = None
    unique_authors_1d: int | None = None
    unique_authors_7d: int | None = None
    relevance_score: float | None = None
    growth_rate_30d: float | None = None
    bot_ratio: float | None = None
    spam_ratio: float | None = None


@dataclass(slots=True)
class CommunityScoreResult:
    total_score: float
    activity_score: float
    relevance_score: float
    freshness_score: float
    audience_quality_score: float
    growth_score: float
    size_score: float
    penalty: float

    def as_dict(self) -> dict[str, float]:
        return {
            "total_score": self.total_score,
            "activity_score": self.activity_score,
            "relevance_score": self.relevance_score,
            "freshness_score": self.freshness_score,
            "audience_quality_score": self.audience_quality_score,
            "growth_score": self.growth_score,
            "size_score": self.size_score,
            "penalty": self.penalty,
        }


@dataclass(slots=True)
class AudienceScoreInput:
    last_activity_at: datetime | None = None
    messages_7d: int = 0
    messages_30d: int = 0
    communities_count: int = 1
    relevance_score: float | None = None
    intent_score: float | None = None
    is_bot: bool = False
    is_fake: bool = False
    is_scam: bool = False
    is_blacklisted: bool = False


@dataclass(slots=True)
class AudienceScoreResult:
    activity_score: float
    quality_score: float
    relevance_score: float
    intent_score: float
    readiness_score: float

    def as_dict(self) -> dict[str, float]:
        return {
            "activity_score": self.activity_score,
            "quality_score": self.quality_score,
            "relevance_score": self.relevance_score,
            "intent_score": self.intent_score,
            "readiness_score": self.readiness_score,
        }


def score_community(data: CommunityScoreInput) -> CommunityScoreResult:
    participants = max(data.participants_count or 0, 0)
    active_7d = max(data.active_7d or 0, 0)
    authors_7d = max(data.unique_authors_7d or 0, 0)
    messages_7d = max(data.messages_7d or 0, 0)
    messages_1d = max(data.messages_1d or 0, 0)

    active_ratio = (active_7d / participants) if participants else 0.0
    author_ratio = (authors_7d / participants) if participants else 0.0
    messages_per_active = (messages_7d / active_7d) if active_7d else 0.0

    activity_score = _clamp(
        active_ratio * 140.0
        + author_ratio * 110.0
        + min(messages_per_active / 4.0, 1.0) * 25.0
    )

    relevance_score = _clamp(float(data.relevance_score or 0.0))

    daily_baseline = (messages_7d / 7.0) if messages_7d else 0.0
    if daily_baseline <= 0:
        freshness_score = 0.0
    else:
        freshness_score = _clamp((messages_1d / daily_baseline) * 65.0)

    bot_ratio = _clamp((data.bot_ratio or 0.0) * 100.0)
    spam_ratio = _clamp((data.spam_ratio or 0.0) * 100.0)
    audience_quality_score = _clamp(100.0 - bot_ratio * 0.75 - spam_ratio * 0.85)

    growth = float(data.growth_rate_30d or 0.0)
    growth_score = _clamp(50.0 + growth * 250.0)

    if participants <= 0:
        size_score = 0.0
    elif participants < 300:
        size_score = 30.0
    elif participants < 1_000:
        size_score = 55.0
    elif participants < 5_000:
        size_score = 75.0
    elif participants < 50_000:
        size_score = 90.0
    else:
        size_score = 100.0

    penalty = _clamp(bot_ratio * 0.20 + spam_ratio * 0.30, 0.0, 35.0)

    weighted = (
        activity_score * 0.25
        + relevance_score * 0.20
        + freshness_score * 0.15
        + audience_quality_score * 0.15
        + growth_score * 0.10
        + size_score * 0.05
        + min(messages_per_active * 15.0, 100.0) * 0.10
    )
    total = _clamp(weighted - penalty)

    return CommunityScoreResult(
        total_score=round(total, 2),
        activity_score=round(activity_score, 2),
        relevance_score=round(relevance_score, 2),
        freshness_score=round(freshness_score, 2),
        audience_quality_score=round(audience_quality_score, 2),
        growth_score=round(growth_score, 2),
        size_score=round(size_score, 2),
        penalty=round(penalty, 2),
    )


def score_audience_member(
    data: AudienceScoreInput,
    *,
    now: datetime | None = None,
) -> AudienceScoreResult:
    now = now or datetime.now(timezone.utc)
    last_activity = data.last_activity_at
    if last_activity and last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)

    recency_points = 0.0
    if last_activity is not None:
        age_days = max((now - last_activity).total_seconds() / 86400.0, 0.0)
        if age_days <= 1:
            recency_points = 40.0
        elif age_days <= 3:
            recency_points = 34.0
        elif age_days <= 7:
            recency_points = 28.0
        elif age_days <= 14:
            recency_points = 18.0
        elif age_days <= 30:
            recency_points = 10.0

    messages_7d = max(data.messages_7d, 0)
    messages_30d = max(data.messages_30d, 0)
    communities = max(data.communities_count, 1)

    activity_score = _clamp(
        recency_points
        + min(messages_7d, 20) / 20.0 * 35.0
        + min(messages_30d, 60) / 60.0 * 15.0
        + min(max(communities - 1, 0), 4) / 4.0 * 10.0
    )

    quality_score = 100.0
    if data.is_bot:
        quality_score -= 100.0
    if data.is_fake:
        quality_score -= 55.0
    if data.is_scam:
        quality_score -= 70.0
    if data.is_blacklisted:
        quality_score = 0.0
    quality_score = _clamp(quality_score)

    relevance_score = _clamp(float(data.relevance_score or 0.0))
    intent_score = _clamp(float(data.intent_score or 0.0))

    readiness = _clamp(
        activity_score * 0.45
        + relevance_score * 0.20
        + quality_score * 0.15
        + intent_score * 0.20
    )
    if data.is_bot or data.is_blacklisted:
        readiness = 0.0

    return AudienceScoreResult(
        activity_score=round(activity_score, 2),
        quality_score=round(quality_score, 2),
        relevance_score=round(relevance_score, 2),
        intent_score=round(intent_score, 2),
        readiness_score=round(readiness, 2),
    )
