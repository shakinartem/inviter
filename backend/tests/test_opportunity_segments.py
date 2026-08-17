from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.features.orchestration.campaign_api import CampaignCreateFromCommunityRequest
from app.features.segments.schemas import SegmentCreate, SegmentCriteria


class OpportunitySegmentTests(unittest.TestCase):
    def test_signal_types_are_normalized_and_deduplicated(self) -> None:
        criteria = SegmentCriteria(
            signal_types=[
                "Transaction Intent",
                "transaction_intent",
                " NEED_INTENT ",
                "",
            ]
        )
        self.assertEqual(
            criteria.signal_types,
            ["transaction_intent", "need_intent"],
        )

    def test_segment_roundtrip_preserves_uuid_community_scope(self) -> None:
        community_id = uuid4()
        criteria = SegmentCriteria(
            min_intent_score=50,
            min_readiness_score=60,
            community_ids=[community_id],
        )
        restored = SegmentCriteria.model_validate(criteria.model_dump(mode="json"))
        self.assertEqual(restored.community_ids, [community_id])
        self.assertEqual(restored.min_intent_score, 50)
        self.assertEqual(restored.min_readiness_score, 60)

    def test_score_threshold_cannot_exceed_100(self) -> None:
        with self.assertRaises(ValidationError):
            SegmentCriteria(min_readiness_score=101)

    def test_segment_member_cap_is_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            SegmentCriteria(max_members=50001)

    def test_segment_defaults_to_interpretable_readiness_sort(self) -> None:
        payload = SegmentCreate(name="Hot intent", criteria=SegmentCriteria())
        self.assertEqual(payload.platform, "telegram")
        self.assertEqual(payload.criteria.sort_by, "readiness")
        self.assertFalse(payload.criteria.include_bots)

    def test_modern_campaign_requires_source_segment(self) -> None:
        with self.assertRaises(ValidationError):
            CampaignCreateFromCommunityRequest(
                title="Campaign",
                target_community_id=uuid4(),
            )

    def test_modern_campaign_accepts_explicit_opportunity(self) -> None:
        payload = CampaignCreateFromCommunityRequest(
            title="Campaign",
            target_community_id=uuid4(),
            source_segment_id=uuid4(),
        )
        self.assertIsNotNone(payload.source_segment_id)


if __name__ == "__main__":
    unittest.main()
