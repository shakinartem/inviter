from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


MODEL_VERSION = "intent-lexical-v1"

_WORD_RE = re.compile(r"[\wа-яё]+", re.IGNORECASE)
_MONEY_RE = re.compile(
    r"(?:\b\d[\d\s.,]{0,12}\s?(?:тыс|млн|миллион|руб|р\.|usd|eur)\b|[₽$€]\s?\d[\d\s.,]{0,12})",
    re.IGNORECASE,
)

# Transparent bootstrap model. It creates labelled/versioned evidence that can
# later train and calibrate a statistical or LLM scorer without losing history.
DIMENSIONS: dict[str, tuple[tuple[str, ...], float]] = {
    "transaction": (
        (
            "хочу купить", "готов купить", "купить", "заказать", "записаться", "оформить",
            "беру", "возьму", "нужна покупка", "готов оплатить", "куплю",
            "want to buy", "ready to buy", "buy", "purchase", "order", "book", "hire",
            "ready to pay", "sign up",
        ),
        32.0,
    ),
    "need_search": (
        (
            "ищу", "нужен", "нужна", "нужно", "требуется", "подскажите", "посоветуйте",
            "кто знает", "где найти", "где купить", "подобрать", "подбор", "ищем",
            "looking for", "need", "searching for", "where can i find", "where to buy",
            "recommend", "recommendation", "anyone know",
        ),
        24.0,
    ),
    "evaluation": (
        (
            "что лучше", "какой лучше", "какая лучше", "сравнить", "сравниваю", "выбираю",
            "варианты", "отзывы", "опыт", "стоит ли", "условия", "предложения",
            "which is better", "compare", "comparing", "choosing", "options", "reviews",
            "worth it", "best option", "recommend",
        ),
        16.0,
    ),
    "budget_price": (
        (
            "цена", "стоимость", "сколько стоит", "бюджет", "руб", "₽", "ипотека",
            "рассрочка", "кредит", "ставка", "платеж", "платёж",
            "price", "cost", "how much", "budget", "quote", "mortgage", "financing",
            "monthly payment",
        ),
        14.0,
    ),
    "urgency": (
        (
            "срочно", "сегодня", "завтра", "на этой неделе", "как можно быстрее", "быстро",
            "urgent", "today", "tomorrow", "this week", "asap", "as soon as possible",
        ),
        10.0,
    ),
    "timeline": (
        (
            "в этом месяце", "в следующем месяце", "в ближайшее время", "планирую",
            "собираюсь", "в течение", "до конца", "срок",
            "this month", "next month", "soon", "planning to", "plan to", "within",
            "by the end",
        ),
        8.0,
    ),
}

SUPPLY_MARKERS = (
    "продаю", "предлагаю", "наша компания", "наши услуги", "акция", "скидка",
    "подписывайтесь", "реклама", "пишите в личку", "мы поможем", "мы предлагаем",
    "for sale", "we offer", "our service", "discount", "promotion", "subscribe",
)

STOPWORDS = {
    "и", "или", "в", "на", "для", "по", "с", "из", "к", "у", "о", "об", "это", "как",
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "about",
}


@dataclass(slots=True)
class IntentEvidence:
    signal_type: str
    score: float
    confidence: float
    model_version: str
    features: dict


@dataclass(slots=True)
class IntentAggregate:
    score: float
    strongest_signal_type: str | None
    signals_count: int


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def _topic_tokens(topic: str | None) -> set[str]:
    if not topic:
        return set()
    return {
        token.casefold().replace("ё", "е")
        for token in _WORD_RE.findall(topic)
        if len(token) >= 3 and token.casefold() not in STOPWORDS
    }


def _match_topic_terms(topic_terms: set[str], message_tokens: set[str]) -> list[str]:
    matched: set[str] = set(topic_terms & message_tokens)
    # Lightweight morphology tolerance for RU/EN inflections. Only long terms are
    # prefix-matched so short generic words do not create false relevance.
    for topic_term in topic_terms:
        if topic_term in matched or len(topic_term) < 5:
            continue
        prefix = topic_term[: max(4, min(7, len(topic_term) - 2))]
        if any(token.startswith(prefix) for token in message_tokens if len(token) >= 5):
            matched.add(topic_term)
    return sorted(matched)


def score_message(
    text: str,
    *,
    topic: str | None = None,
    minimum_score: float = 12.0,
) -> IntentEvidence | None:
    normalized = _normalize(text)
    if len(normalized) < 3:
        return None

    matched_dimensions: dict[str, list[str]] = {}
    dimension_scores: dict[str, float] = {}
    for dimension, (phrases, max_points) in DIMENSIONS.items():
        matched = [phrase for phrase in phrases if phrase in normalized]
        if not matched:
            continue
        strength = min(1.0, 0.70 + 0.15 * (len(set(matched)) - 1))
        matched_dimensions[dimension] = sorted(set(matched))[:8]
        dimension_scores[dimension] = max_points * strength

    money_matches = sorted(set(match.group(0).strip() for match in _MONEY_RE.finditer(text)))[:6]
    if money_matches:
        matched_dimensions.setdefault("budget_price", []).extend(money_matches)
        dimension_scores["budget_price"] = max(dimension_scores.get("budget_price", 0.0), 11.0)

    topic_terms = _topic_tokens(topic)
    message_tokens = {
        token.casefold().replace("ё", "е") for token in _WORD_RE.findall(normalized)
    }
    matched_topic_terms = _match_topic_terms(topic_terms, message_tokens)
    if topic_terms:
        topic_ratio = len(matched_topic_terms) / max(len(topic_terms), 1)
        topic_points = min(20.0, topic_ratio * 20.0)
    else:
        topic_points = 5.0 if matched_dimensions else 0.0

    question_points = 4.0 if "?" in text and matched_dimensions else 0.0
    supply_matches = [marker for marker in SUPPLY_MARKERS if marker in normalized]
    supply_penalty = min(24.0, len(set(supply_matches)) * 8.0)

    raw_score = sum(dimension_scores.values()) + topic_points + question_points - supply_penalty
    score = max(0.0, min(100.0, raw_score))
    if score < minimum_score:
        return None

    strongest = max(dimension_scores, key=dimension_scores.get) if dimension_scores else "topic_interest"
    signal_type_map = {
        "transaction": "transaction_intent",
        "need_search": "need_intent",
        "evaluation": "evaluation_intent",
        "budget_price": "financial_intent",
        "urgency": "urgency_intent",
        "timeline": "timeline_intent",
        "topic_interest": "topic_interest",
    }

    independent_dimensions = len(dimension_scores)
    confidence = 0.34 + min(independent_dimensions, 4) * 0.11
    if matched_topic_terms:
        confidence += min(len(matched_topic_terms), 3) * 0.07
    if money_matches:
        confidence += 0.05
    if "?" in text:
        confidence += 0.04
    if supply_matches:
        confidence -= 0.12
    confidence = max(0.10, min(0.96, confidence))

    return IntentEvidence(
        signal_type=signal_type_map[strongest],
        score=round(score, 2),
        confidence=round(confidence, 3),
        model_version=MODEL_VERSION,
        features={
            "dimensions": matched_dimensions,
            "dimension_scores": {key: round(value, 2) for key, value in dimension_scores.items()},
            "topic_terms": matched_topic_terms[:12],
            "topic_points": round(topic_points, 2),
            "money_mentions": money_matches,
            "question_signal": question_points > 0,
            "supply_markers": sorted(set(supply_matches))[:8],
            "supply_penalty": round(supply_penalty, 2),
        },
    )


def aggregate_intent(
    signals: Iterable[tuple[float, float, datetime, str]],
    *,
    now: datetime | None = None,
    half_life_days: float = 14.0,
) -> IntentAggregate:
    """Aggregate `(score, confidence, observed_at, signal_type)` evidence.

    Recent signals dominate but repeated independent signals increase certainty.
    The result remains 0..100 and can be recomputed whenever the model changes.
    """
    now = now or datetime.now(timezone.utc)
    weighted: list[tuple[float, str]] = []
    for score, confidence, observed_at, signal_type in signals:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        age_days = max((now - observed_at).total_seconds() / 86400.0, 0.0)
        decay = math.pow(0.5, age_days / max(half_life_days, 0.1))
        weighted_score = max(0.0, min(100.0, score)) * max(0.0, min(1.0, confidence)) * decay
        weighted.append((weighted_score, signal_type))

    if not weighted:
        return IntentAggregate(score=0.0, strongest_signal_type=None, signals_count=0)

    weighted.sort(key=lambda item: item[0], reverse=True)
    strongest_score, strongest_type = weighted[0]
    top = weighted[:5]
    mean_top = sum(item[0] for item in top) / len(top)
    repetition_bonus = min(max(len(weighted) - 1, 0) * 2.5, 12.5)
    aggregate = min(100.0, strongest_score * 0.68 + mean_top * 0.32 + repetition_bonus)

    return IntentAggregate(
        score=round(aggregate, 2),
        strongest_signal_type=strongest_type,
        signals_count=len(weighted),
    )
