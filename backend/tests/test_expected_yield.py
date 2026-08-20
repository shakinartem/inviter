from __future__ import annotations

import unittest

from app.api.router import api_router
from app.features.segments.forecast import SegmentYieldForecastService


class ExpectedYieldContractTests(unittest.TestCase):
    def test_readiness_buckets_cover_boundary_scores(self) -> None:
        bucket = SegmentYieldForecastService._readiness_bucket
        self.assertEqual(bucket(0), 0)
        self.assertEqual(bucket(19.99), 0)
        self.assertEqual(bucket(20), 20)
        self.assertEqual(bucket(79.9), 60)
        self.assertEqual(bucket(80), 80)
        self.assertEqual(bucket(100), 80)
        self.assertEqual(bucket(120), 80)

    def test_beta_posterior_is_bounded(self) -> None:
        mean, low, high = SegmentYieldForecastService._beta_summary(5.5, 15.5)
        self.assertGreater(mean, 0)
        self.assertLess(mean, 1)
        self.assertGreaterEqual(low, 0)
        self.assertLessEqual(high, 1)
        self.assertLessEqual(low, mean)
        self.assertGreaterEqual(high, mean)

    def test_beta_binomial_uncertainty_grows_with_budget(self) -> None:
        small = SegmentYieldForecastService._beta_binomial_variance(10, 10, 30)
        large = SegmentYieldForecastService._beta_binomial_variance(100, 10, 30)
        self.assertGreater(large, small)

    def test_forecast_route_is_registered_before_generic_segment_route(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        forecast_index = paths.index("/segments/{segment_id}/forecast")
        dynamic_index = paths.index("/segments/{segment_id}")
        self.assertLess(forecast_index, dynamic_index)


if __name__ == "__main__":
    unittest.main()
