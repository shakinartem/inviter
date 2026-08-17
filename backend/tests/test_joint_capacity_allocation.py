from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.features.allocations.service import CapacityAllocationService


class JointCapacityAllocationContractTests(unittest.TestCase):
    def test_offer_key_prioritizes_conservative_incremental_value(self) -> None:
        stronger = {
            "low": 0.03,
            "effect": 0.04,
            "source": "stable_global_prior",
            "segment_rank": 50,
        }
        weaker = {
            "low": 0.02,
            "effect": 0.10,
            "source": "replicated_context",
            "segment_rank": 1,
        }
        self.assertGreater(
            CapacityAllocationService._offer_key(stronger),
            CapacityAllocationService._offer_key(weaker),
        )

    def test_replicated_context_overrides_global_prior(self) -> None:
        member = SimpleNamespace(readiness_score=65.0, strongest_signal_type="need_intent")
        evidence = CapacityAllocationService._evidence_for_member(
            member=member,
            contextual_rows={
                ("60-79", "need_intent"): {
                    "evidence_status": "replicated",
                    "shrunk_lift_percentage_points": 5.0,
                    "confidence_low_percentage_points": 2.0,
                    "confidence_high_percentage_points": 8.0,
                }
            },
            global_effect=0.01,
            global_low=0.005,
            global_high=0.015,
            global_status="positive",
            stable_global=True,
            allocation_mode="decision_grade",
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence["source"], "replicated_context")
        self.assertEqual(evidence["effect"], 0.05)

    def test_decision_grade_rejects_unstable_global_fallback(self) -> None:
        member = SimpleNamespace(readiness_score=40.0, strongest_signal_type=None)
        evidence = CapacityAllocationService._evidence_for_member(
            member=member,
            contextual_rows={},
            global_effect=0.03,
            global_low=-0.01,
            global_high=0.07,
            global_status="heterogeneous",
            stable_global=False,
            allocation_mode="decision_grade",
        )
        self.assertIsNone(evidence)

    def test_coverage_expansion_can_use_labeled_global_fallback(self) -> None:
        member = SimpleNamespace(readiness_score=40.0, strongest_signal_type=None)
        evidence = CapacityAllocationService._evidence_for_member(
            member=member,
            contextual_rows={},
            global_effect=0.03,
            global_low=-0.01,
            global_high=0.07,
            global_status="heterogeneous",
            stable_global=False,
            allocation_mode="coverage_expansion",
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence["source"], "global_prior_fallback")


if __name__ == "__main__":
    unittest.main()
