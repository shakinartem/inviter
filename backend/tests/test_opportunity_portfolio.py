from __future__ import annotations

import unittest
from uuid import uuid4

from app.api.router import api_router
from app.features.segments.portfolio_schemas import OpportunityPortfolioResponse


class OpportunityPortfolioContractTests(unittest.TestCase):
    def test_static_portfolio_route_precedes_dynamic_forecast_route(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        portfolio_index = paths.index("/segments/portfolio/forecast")
        dynamic_forecast_index = paths.index("/segments/{segment_id}/forecast")
        self.assertLess(portfolio_index, dynamic_forecast_index)

    def test_response_allows_no_recommendation_when_evidence_is_weak(self) -> None:
        response = OpportunityPortfolioResponse.model_validate(
            {
                "stage": "business",
                "event_type": "converted",
                "horizon_hours": 168,
                "action_budget": 1000,
                "ranking_basis": "quality_adjusted_conservative_expected_outcomes",
                "recommendation_segment_id": None,
                "recommendation_name": None,
                "warnings": ["no_high_confidence_recommendation"],
                "rows": [
                    {
                        "rank": 1,
                        "segment_id": str(uuid4()),
                        "segment_name": "Sparse cohort",
                        "matched_count": 500,
                        "evaluated_members": 500,
                        "expected_outcomes": 30,
                        "conservative_outcomes": 10,
                        "upside_outcomes": 55,
                        "expected_rate": 6,
                        "conservative_rate": 2,
                        "quality_status": "limited",
                        "frozen_history_ratio": 40,
                        "contextual_coverage": 35,
                        "score": 7.5,
                        "warnings": ["observational_not_causal"],
                    }
                ],
            }
        )
        self.assertIsNone(response.recommendation_segment_id)
        self.assertEqual(response.rows[0].quality_status, "limited")


if __name__ == "__main__":
    unittest.main()
