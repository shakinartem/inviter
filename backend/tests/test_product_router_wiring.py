from __future__ import annotations

import unittest

from app.api.router import api_router


class ProductRouterWiringTests(unittest.TestCase):
    def test_intent_intelligence_workspaces_are_reachable(self) -> None:
        paths = {getattr(route, "path", None) for route in api_router.routes}
        expected = {
            "/experiments/power-plan",
            "/experiments/meta-lift",
            "/experiments/contextual-lift",
            "/experiments/value-lift",
            "/experiments/contextual-value",
            "/experiments/evidence-health",
            "/segments/causal-portfolio/forecast",
            "/allocations/capacity-frontier",
            "/allocations/plans",
            "/account-capacity/policy",
            "/account-capacity/refresh",
            "/account-capacity/forecast",
            "/adaptive-execution/policy",
            "/adaptive-execution/preview",
            "/adaptive-execution/rebalance",
            "/adaptive-execution/events",
            "/adaptive-execution/resilience/{campaign_id}",
            "/orchestration/campaigns/{campaign_id}/preflight",
            "/orchestration/campaigns/{campaign_id}/preflight/start",
            "/execution-sla/forecast",
            "/execution-sla/finalize",
            "/execution-sla/calibration",
            "/execution-sla/continuity-calibration",
            "/execution-sla/labels",
            "/execution-sla/history",
            "/execution-sla/calibrators",
            "/execution-sla/calibrators/live-health",
            "/execution-sla/calibrators/train",
            "/execution-sla/calibrators/{calibrator_id}/activate",
            "/execution-sla/calibrators/{calibrator_id}/retire",
            "/execution-events",
        }
        self.assertTrue(expected.issubset(paths), f"Missing routes: {sorted(expected - paths)}")


if __name__ == "__main__":
    unittest.main()
