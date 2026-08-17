from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.features.intelligence.intent import MODEL_VERSION, aggregate_intent, score_message


class IntentScoringTests(unittest.TestCase):
    def test_high_intent_ru_purchase_message(self) -> None:
        evidence = score_message(
            "Ищу квартиру в Москве, хочу купить в этом месяце. Бюджет 20 млн ₽, что лучше выбрать?",
            topic="квартиры недвижимость Москва",
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertGreaterEqual(evidence.score, 60)
        self.assertEqual(evidence.model_version, MODEL_VERSION)
        dimensions = evidence.features["dimensions"]
        self.assertIn("transaction", dimensions)
        self.assertIn("need_search", dimensions)
        self.assertIn("budget_price", dimensions)
        self.assertTrue(evidence.features["money_mentions"])
        self.assertGreater(evidence.confidence, 0.6)

    def test_high_intent_english_search_message(self) -> None:
        evidence = score_message(
            "Looking for an AI automation agency this month. What is the price and which option is better?",
            topic="AI automation",
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertGreaterEqual(evidence.score, 40)
        self.assertIn(evidence.signal_type, {"need_intent", "evaluation_intent", "financial_intent"})

    def test_generic_chat_is_not_intent(self) -> None:
        self.assertIsNone(score_message("Доброе утро всем!", topic="недвижимость"))

    def test_promotional_supply_is_penalized(self) -> None:
        demand = score_message(
            "Ищу квартиру, бюджет 15 млн, хочу купить срочно",
            topic="квартира",
        )
        supply = score_message(
            "Продаю квартиру, наша компания предлагает скидку, пишите в личку",
            topic="квартира",
        )
        self.assertIsNotNone(demand)
        demand_score = demand.score if demand else 0.0
        supply_score = supply.score if supply else 0.0
        self.assertGreater(demand_score, supply_score)

    def test_topic_morphology_tolerance(self) -> None:
        evidence = score_message(
            "Ищу варианты по квартирам, подскажите что лучше?",
            topic="квартира",
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertIn("квартира", evidence.features["topic_terms"])

    def test_aggregate_rewards_recent_repeated_signals(self) -> None:
        now = datetime.now(timezone.utc)
        one = aggregate_intent(
            [(80.0, 0.8, now, "transaction_intent")],
            now=now,
        )
        repeated = aggregate_intent(
            [
                (80.0, 0.8, now, "transaction_intent"),
                (70.0, 0.75, now - timedelta(days=1), "financial_intent"),
                (65.0, 0.7, now - timedelta(days=2), "evaluation_intent"),
            ],
            now=now,
        )
        stale = aggregate_intent(
            [(80.0, 0.8, now - timedelta(days=45), "transaction_intent")],
            now=now,
        )
        self.assertGreater(repeated.score, one.score)
        self.assertGreater(one.score, stale.score)


if __name__ == "__main__":
    unittest.main()
