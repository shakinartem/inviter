from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.features.experiments.service import CampaignExperimentService
from app.features.orchestration.campaign_api import CampaignCreateFromCommunityRequest


class RandomizedHoldoutContractTests(unittest.TestCase):
    def test_required_pool_preserves_requested_treatment_budget(self) -> None:
        service = CampaignExperimentService
        pool = service.required_pool_size(action_budget=1000, holdout_percentage=10)
        holdout = service.holdout_count_for_pool(
            pool_size=pool,
            action_budget=1000,
            holdout_percentage=10,
            full_pool_available=True,
        )
        self.assertEqual(pool - holdout, 1000)
        self.assertGreater(holdout, 0)

    def test_exact_treatment_budget_at_fifty_percent_holdout(self) -> None:
        service = CampaignExperimentService
        pool = service.required_pool_size(action_budget=500, holdout_percentage=50)
        holdout = service.holdout_count_for_pool(
            pool_size=pool,
            action_budget=500,
            holdout_percentage=50,
            full_pool_available=True,
        )
        self.assertEqual(pool, 1000)
        self.assertEqual(holdout, 500)

    def test_small_pool_keeps_at_least_one_treatment(self) -> None:
        holdout = CampaignExperimentService.holdout_count_for_pool(
            pool_size=3,
            action_budget=100,
            holdout_percentage=50,
            full_pool_available=False,
        )
        self.assertEqual(holdout, 2)
        self.assertEqual(3 - holdout, 1)

    def test_holdout_selection_is_deterministic_and_order_independent(self) -> None:
        members = [uuid4() for _ in range(20)]
        first = CampaignExperimentService.select_holdout_ids(
            member_ids=members,
            holdout_count=4,
            assignment_salt="fixed-test-salt",
        )
        second = CampaignExperimentService.select_holdout_ids(
            member_ids=list(reversed(members)),
            holdout_count=4,
            assignment_salt="fixed-test-salt",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)

    def test_different_salt_changes_assignment(self) -> None:
        members = [uuid4() for _ in range(50)]
        first = CampaignExperimentService.select_holdout_ids(
            member_ids=members,
            holdout_count=10,
            assignment_salt="salt-a",
        )
        second = CampaignExperimentService.select_holdout_ids(
            member_ids=members,
            holdout_count=10,
            assignment_salt="salt-b",
        )
        self.assertNotEqual(first, second)

    def test_campaign_contract_rejects_excessive_holdout(self) -> None:
        with self.assertRaises(ValidationError):
            CampaignCreateFromCommunityRequest.model_validate(
                {
                    "title": "Experiment",
                    "target_community_id": str(uuid4()),
                    "source_segment_id": str(uuid4()),
                    "holdout_percentage": 51,
                }
            )

    def test_campaign_contract_defaults_to_no_hidden_holdout(self) -> None:
        payload = CampaignCreateFromCommunityRequest.model_validate(
            {
                "title": "No experiment",
                "target_community_id": str(uuid4()),
                "source_segment_id": str(uuid4()),
            }
        )
        self.assertEqual(payload.holdout_percentage, 0)


if __name__ == "__main__":
    unittest.main()
