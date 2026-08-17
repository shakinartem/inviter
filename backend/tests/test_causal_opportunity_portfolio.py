from __future__ import annotations

import unittest

from app.api.router import api_router
from app.features.segments.causal_portfolio import CausalOpportunityPortfolioService


class CausalOpportunityPortfolioContractTests(unittest.TestCase):
    def test_static_causal_portfolio_route_precedes_dynamic_segment_routes(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        causal_index = paths.index("/segments/causal-portfolio/forecast")
        dynamic_index = paths.index("/segments/{segment_id}/forecast")
        self.assertLess(causal_index, dynamic_index)

    def test_bucket_labels_match_contextual_estimator(self) -> None:
        bucket = CausalOpportunityPortfolioService._bucket_label
        self.assertEqual(bucket(0), "0-19")
        self.assertEqual(bucket(19.9), "0-19")
        self.assertEqual(bucket(20), "20-39")
        self.assertEqual(bucket(80), "80-100")
        self.assertEqual(bucket(100), "80-100")


if __name__ == "__main__":
    unittest.main()
