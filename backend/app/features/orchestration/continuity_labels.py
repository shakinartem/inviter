from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class ContinuityWindow:
    index: int
    start_at: datetime
    end_at: datetime
    required_actions: int
    successful_actions: int
    met: bool


@dataclass(frozen=True, slots=True)
class ContinuityLabel:
    met_continuity: bool
    windows_total: int
    windows_met: int
    continuity_rate: float
    remaining_actions_at_deadline: int
    windows: tuple[ContinuityWindow, ...]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def label_execution_continuity(
    *,
    forecast_created_at: datetime,
    deadline_at: datetime,
    normal_daily_capacity: int,
    remaining_actions: int,
    successful_finished_at: list[datetime],
) -> ContinuityLabel:
    """Label forecast-relative 24h schedule continuity.

    Each 24h window must deliver the promised normal rate, capped by the
    remaining workload. Finishing early ends the obligation. Over-delivery can
    reduce future remaining workload but can never erase a previously missed
    window.

    Continuity is deliberately independent from fixed-workload completion: a
    workload may exceed available normal capacity yet still maintain its promised
    cadence in every window. Completion-by-deadline is labeled separately.
    """
    start = _aware(forecast_created_at)
    deadline = _aware(deadline_at)
    if deadline <= start:
        raise ValueError("deadline_at must be after forecast_created_at")
    daily = max(int(normal_daily_capacity), 1)
    remaining = max(int(remaining_actions), 0)
    successes = sorted(_aware(item) for item in successful_finished_at if start < _aware(item) <= deadline)

    windows: list[ContinuityWindow] = []
    cursor = start
    index = 0
    while cursor < deadline and remaining > 0:
        end = min(cursor + timedelta(hours=24), deadline)
        hours = max((end - cursor).total_seconds() / 3600.0, 0.0)
        prorated = max(int(math.ceil(daily * min(hours / 24.0, 1.0))), 1)
        required = min(prorated, remaining)
        actual = sum(1 for item in successes if cursor < item <= end)
        met = actual >= required
        windows.append(
            ContinuityWindow(
                index=index,
                start_at=cursor,
                end_at=end,
                required_actions=required,
                successful_actions=actual,
                met=met,
            )
        )
        remaining = max(remaining - actual, 0)
        cursor = end
        index += 1

    total = len(windows)
    met_count = sum(1 for item in windows if item.met)
    met_continuity = (total == 0 and remaining == 0) or (total > 0 and met_count == total)
    rate = (met_count / total) if total else (1.0 if remaining == 0 else 0.0)
    return ContinuityLabel(
        met_continuity=met_continuity,
        windows_total=total,
        windows_met=met_count,
        continuity_rate=round(rate, 6),
        remaining_actions_at_deadline=remaining,
        windows=tuple(windows),
    )
