from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreflightBudgetRecommendation:
    required_daily_rate: int
    maximum_safe_action_budget: int
    recommended_action_budget: int
    recommended_deadline_days: int | None
    budget_reduction_needed: bool
    deadline_extension_needed: bool
    estimated_completion_days: float | None


def recommend_preflight_budget(
    *,
    requested_actions: int,
    executable_actions: int,
    normal_daily_capacity: int,
    deadline_days: int,
) -> PreflightBudgetRecommendation:
    """Recommend an actionable workload/deadline pair from actual executable work.

    `required_daily_rate` is based on the cohort the planner can actually execute,
    not on an inflated requested budget. The safe budget is bounded by both that
    executable cohort and normal (reserve-respecting) capacity over the horizon.
    """
    requested = max(int(requested_actions), 0)
    executable = max(min(int(executable_actions), requested), 0)
    daily = max(int(normal_daily_capacity), 0)
    horizon = max(int(deadline_days), 1)

    required_daily_rate = math.ceil(executable / horizon) if executable > 0 else 0
    maximum_safe = min(executable, daily * horizon) if daily > 0 else 0
    recommended_budget = min(requested, maximum_safe)
    recommended_deadline = math.ceil(executable / daily) if executable > 0 and daily > 0 else None
    estimated_days = round(executable / daily, 2) if executable > 0 and daily > 0 else None

    return PreflightBudgetRecommendation(
        required_daily_rate=required_daily_rate,
        maximum_safe_action_budget=maximum_safe,
        recommended_action_budget=recommended_budget,
        recommended_deadline_days=recommended_deadline,
        budget_reduction_needed=recommended_budget < requested,
        deadline_extension_needed=(recommended_deadline is not None and recommended_deadline > horizon),
        estimated_completion_days=estimated_days,
    )
