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
        }
        self.assertTrue(expected.issubset(paths), f"Missing routes: {sorted(expected - paths)}")


if __name__ == "__main__":
    unittest.main()
