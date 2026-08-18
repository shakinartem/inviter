from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import HARD_COOLDOWN_CODES, AccountCapacityRiskService
from app.features.accounts.models import Account
from app.features.inviter.models import InviteCampaign
from app.features.orchestration.models import ActionJob
from app.features.orchestration.service import OrchestrationService
from app.features.orchestration.sla_models import ExecutionSLAForecastSnapshot
from app.features.orchestration.sla_schemas import (
    AccountHazardResponse,
    ExecutionSLAForecastHistoryItem,
    ExecutionSLAForecastResponse,
    SLAScenarioResponse,
)


MODEL_VERSION = "execution-sla-v1"
PRIOR_ALPHA = 1.0
PRIOR_BETA = 19.0
DEFAULT_RESERVES = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0)


def posterior_daily_hazard(*, hard_failure_days: int, exposure_days: int) -> float:
    hard = max(min(int(hard_failure_days), int(exposure_days)), 0)
    exposure = max(int(exposure_days), 0)
    return (PRIOR_ALPHA + hard) / (PRIOR_ALPHA + PRIOR_BETA + exposure)


def wilson_upper(*, successes: float, total: float, z: float = 1.96) -> float:
    n = max(float(total), 1.0)
    p = min(max(float(successes) / n, 0.0), 1.0)
    z2 = z * z
    center = p + z2 / (2.0 * n)
    spread = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    upper = (center + spread) / (1.0 + z2 / n)
    return min(max(upper, p), 1.0)


def conservative_daily_hazard(*, hard_failure_days: int, exposure_days: int) -> float:
    successes = PRIOR_ALPHA + max(int(hard_failure_days), 0)
    total = PRIOR_ALPHA + PRIOR_BETA + max(int(exposure_days), 0)
    return min(wilson_upper(successes=successes, total=total), 0.95)


def account_evidence_quality(exposure_days: int) -> str:
    if exposure_days >= 30:
        return "strong"
    if exposure_days >= 10:
        return "usable"
    if exposure_days > 0:
        return "limited"
    return "prior_only"


def pool_evidence_quality(exposure_days: list[int]) -> str:
    if not exposure_days:
        return "insufficient"
    total = sum(exposure_days)
    accounts = len(exposure_days)
    if total >= max(60, accounts * 20) and min(exposure_days) >= 10:
        return "strong"
    if total >= max(20, accounts * 5):
        return "usable"
    return "limited"


def normal_capacity(emergency_capacity: int, reserve_percentage: float) -> int:
    emergency = max(int(emergency_capacity), 0)
    if emergency <= 0:
        return 0
    reserve = min(max(float(reserve_percentage), 0.0), 50.0)
    return min(max(int(emergency * (1.0 - reserve / 100.0)), 1), emergency)


def simulate_sla_scenarios(
    *,
    emergency_capacities: list[int],
    hazards: list[float],
    reserve_percentages: list[float],
    remaining_actions: int,
    deadline_days: int,
    simulations: int,
    seed: int,
) -> dict[float, tuple[float, float, float]]:
    """Return reserve -> (schedule continuity, workload completion, expected actions).

    Schedule continuity means physical surviving capacity stayed at or above the
    normal committed throughput on every day in the horizon. Reserve can improve
    this metric because it lowers the promised normal rate without increasing the
    platform's physical emergency ceiling.
    """
    if len(emergency_capacities) != len(hazards):
        raise ValueError("capacity and hazard vectors must have equal length")
    reserves = [min(max(float(item), 0.0), 50.0) for item in reserve_percentages]
    normal_totals = {
        reserve: sum(normal_capacity(capacity, reserve) for capacity in emergency_capacities)
        for reserve in reserves
    }
    continuities = {reserve: 0 for reserve in reserves}
    completions = {reserve: 0 for reserve in reserves}
    action_totals = {reserve: 0.0 for reserve in reserves}
    if not emergency_capacities or simulations <= 0:
        return {reserve: (0.0, 0.0, 0.0) for reserve in reserves}

    rng = random.Random(seed)
    for _ in range(simulations):
        cumulative = {reserve: 0 for reserve in reserves}
        continuous = {reserve: True for reserve in reserves}
        for _day in range(deadline_days):
            surviving_emergency = 0
            for capacity, hazard in zip(emergency_capacities, hazards):
                if rng.random() >= min(max(float(hazard), 0.0), 1.0):
                    surviving_emergency += capacity
            for reserve in reserves:
                normal_total = normal_totals[reserve]
                if surviving_emergency < normal_total:
                    continuous[reserve] = False
                cumulative[reserve] += min(normal_total, surviving_emergency)
        for reserve in reserves:
            total = cumulative[reserve]
            action_totals[reserve] += total
            if continuous[reserve]:
                continuities[reserve] += 1
            if total >= remaining_actions:
                completions[reserve] += 1

    return {
        reserve: (
            continuities[reserve] / simulations,
            completions[reserve] / simulations,
            action_totals[reserve] / simulations,
        )
        for reserve in reserves
    }


class ExecutionSLAForecastService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def forecast(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        remaining_actions: int,
        deadline_days: int,
        target_sla: float,
        lookback_days: int,
        reserve_percentages: list[float] | None,
        simulations: int,
        persist_snapshot: bool,
    ) -> ExecutionSLAForecastResponse:
        now = datetime.now(timezone.utc)
        campaign = (
            await self.session.execute(
                select(InviteCampaign).where(
                    InviteCampaign.id == campaign_id,
                    InviteCampaign.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if campaign is None:
            raise ValueError("Campaign not found")

        pool_result = await self.session.execute(
            select(ActionJob.account_id)
            .where(
                ActionJob.owner_id == owner_id,
                ActionJob.campaign_id == campaign_id,
                ActionJob.platform == "telegram",
            )
            .distinct()
        )
        pool_ids = list(pool_result.scalars().all())
        if not pool_ids:
            raise ValueError("Campaign has no assigned account pool yet. Start or plan it first.")

        risk_assessments = await AccountCapacityRiskService(self.session).evaluate_pool(
            owner_id=owner_id,
            platform="telegram",
            campaign_daily_limit=max(int(campaign.daily_limit_per_account), 1),
            account_ids=pool_ids,
            persist_snapshots=False,
        )
        eligible = {item.account_id: item for item in risk_assessments if item.eligible}
        if not eligible:
            raise ValueError("Campaign currently has no safe eligible accounts")

        account_result = await self.session.execute(
            select(Account).where(
                Account.owner_id == owner_id,
                Account.id.in_(eligible.keys()),
            )
        )
        accounts = list(account_result.scalars().all())
        exposure = await self._historical_exposure(
            account_ids=[account.id for account in accounts],
            lookback_days=lookback_days,
            now=now,
        )

        account_rows: list[AccountHazardResponse] = []
        emergency_capacities: list[int] = []
        model_hazards: list[float] = []
        conservative_hazards: list[float] = []
        exposure_days_vector: list[int] = []

        for account in sorted(accounts, key=lambda item: item.label.lower()):
            assessment = eligible[account.id]
            warmup_limit = OrchestrationService._effective_daily_limit(account, campaign, now)
            emergency = max(min(int(assessment.suggested_daily_capacity), int(warmup_limit)), 1)
            metrics = exposure.get(account.id, {"exposure_days": 0, "hard_failure_days": 0})
            exposure_days = int(metrics["exposure_days"])
            hard_days = int(metrics["hard_failure_days"])
            posterior = posterior_daily_hazard(hard_failure_days=hard_days, exposure_days=exposure_days)
            conservative = conservative_daily_hazard(hard_failure_days=hard_days, exposure_days=exposure_days)
            account_rows.append(
                AccountHazardResponse(
                    account_id=account.id,
                    label=account.label,
                    health_score=float(assessment.health_score),
                    emergency_daily_capacity=emergency,
                    exposure_days=exposure_days,
                    hard_failure_days=hard_days,
                    posterior_daily_hazard=round(posterior, 5),
                    conservative_daily_hazard=round(conservative, 5),
                    evidence_quality=account_evidence_quality(exposure_days),
                )
            )
            emergency_capacities.append(emergency)
            model_hazards.append(posterior)
            conservative_hazards.append(conservative)
            exposure_days_vector.append(exposure_days)

        current_reserve = min(max(float(campaign.reserve_capacity_percentage or 0.0), 0.0), 50.0)
        scenario_reserves = sorted({*DEFAULT_RESERVES, current_reserve, *(reserve_percentages or [])})
        required_daily_rate = math.ceil(remaining_actions / deadline_days)

        requested_simulations = max(int(simulations), 500)
        complexity_per_simulation = max(deadline_days * (len(accounts) + len(scenario_reserves)), 1)
        effective_simulations = min(requested_simulations, max(500, 3_000_000 // complexity_per_simulation))

        seed_material = (
            f"{campaign.id}:{remaining_actions}:{deadline_days}:{lookback_days}:"
            f"{','.join(str(item) for item in scenario_reserves)}"
        ).encode()
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
        modelled = simulate_sla_scenarios(
            emergency_capacities=emergency_capacities,
            hazards=model_hazards,
            reserve_percentages=scenario_reserves,
            remaining_actions=remaining_actions,
            deadline_days=deadline_days,
            simulations=effective_simulations,
            seed=seed,
        )
        conservative = simulate_sla_scenarios(
            emergency_capacities=emergency_capacities,
            hazards=conservative_hazards,
            reserve_percentages=scenario_reserves,
            remaining_actions=remaining_actions,
            deadline_days=deadline_days,
            simulations=effective_simulations,
            seed=seed ^ 0x5A17C0DE,
        )

        zero_capacity = sum(normal_capacity(item, 0.0) for item in emergency_capacities)
        emergency_total = sum(emergency_capacities)
        scenarios: list[SLAScenarioResponse] = []
        for reserve in scenario_reserves:
            normal_total = sum(normal_capacity(item, reserve) for item in emergency_capacities)
            model_continuity, model_completion, expected_actions = modelled[reserve]
            conservative_continuity, conservative_completion, conservative_actions = conservative[reserve]
            supports_required_rate = normal_total >= required_daily_rate
            scenarios.append(
                SLAScenarioResponse(
                    reserve_percentage=reserve,
                    normal_daily_capacity=normal_total,
                    emergency_daily_capacity=emergency_total,
                    reserved_headroom=max(emergency_total - normal_total, 0),
                    required_daily_rate=required_daily_rate,
                    supports_required_daily_rate=supports_required_rate,
                    nominal_completion_days=(round(remaining_actions / normal_total, 2) if normal_total > 0 else None),
                    modelled_schedule_continuity_probability=round(model_continuity, 4),
                    conservative_schedule_continuity_probability=round(conservative_continuity, 4),
                    modelled_workload_completion_probability=round(model_completion, 4),
                    conservative_workload_completion_probability=round(conservative_completion, 4),
                    expected_actions_by_deadline=round(expected_actions, 1),
                    conservative_expected_actions_by_deadline=round(conservative_actions, 1),
                    meets_target_sla=(supports_required_rate and conservative_continuity >= target_sla),
                    throughput_penalty_vs_zero_reserve=max(zero_capacity - normal_total, 0),
                )
            )

        current_scenario = min(scenarios, key=lambda item: abs(item.reserve_percentage - current_reserve))
        candidates = [item for item in scenarios if item.meets_target_sla]
        recommended = (
            max(candidates, key=lambda item: (item.normal_daily_capacity, -item.reserve_percentage))
            if candidates
            else None
        )

        quality = pool_evidence_quality(exposure_days_vector)
        total_exposure = sum(exposure_days_vector)
        total_hard = sum(item.hard_failure_days for item in account_rows)
        warnings = [
            "Execution SLA is a modelled operational probability, not a Telegram/platform guarantee.",
            "Reserve improves schedule continuity by lowering committed normal throughput; it does not create physical emergency capacity.",
            "Daily account disruptions are treated as independent; correlated platform incidents can make reality worse.",
            "Historical exposure counts active execution days, so sparse/new accounts are intentionally pulled toward a conservative prior.",
        ]
        if len(eligible) < len(pool_ids):
            warnings.append("Some accounts from the campaign pool are currently quarantined/unavailable and excluded from usable capacity.")
        if quality == "limited":
            warnings.append("Historical account exposure is limited; use this forecast for stress planning, not a contractual SLA.")
        if effective_simulations < requested_simulations:
            warnings.append(f"Simulation count was capped at {effective_simulations} to bound request cost for this pool/horizon.")

        any_supports_rate = any(item.supports_required_daily_rate for item in scenarios)
        if not any_supports_rate:
            status = "workload_exceeds_normal_capacity"
        elif recommended is None:
            status = "continuity_sla_not_supported"
        elif quality == "limited":
            status = "continuity_sla_modelled_but_evidence_limited"
        else:
            status = "continuity_sla_supported"

        deadline_at = now + timedelta(days=deadline_days)
        forecast_id: UUID | None = None
        if persist_snapshot:
            snapshot = ExecutionSLAForecastSnapshot(
                owner_id=owner_id,
                campaign_id=campaign.id,
                model_version=MODEL_VERSION,
                remaining_actions=remaining_actions,
                deadline_at=deadline_at,
                target_sla=target_sla,
                lookback_days=lookback_days,
                evidence_quality=quality,
                current_reserve_percentage=current_reserve,
                recommended_reserve_percentage=(recommended.reserve_percentage if recommended else None),
                recommended_modelled_continuity_probability=(recommended.modelled_schedule_continuity_probability if recommended else None),
                recommended_conservative_continuity_probability=(recommended.conservative_schedule_continuity_probability if recommended else None),
                normal_daily_capacity=current_scenario.normal_daily_capacity,
                emergency_daily_capacity=current_scenario.emergency_daily_capacity,
                input_snapshot={
                    "pool_account_ids": [str(item.account_id) for item in account_rows],
                    "required_daily_rate": required_daily_rate,
                    "total_exposure_days": total_exposure,
                    "total_hard_failure_days": total_hard,
                    "accounts": [item.model_dump(mode="json") for item in account_rows],
                    "simulations": effective_simulations,
                    "objective": "schedule_continuity_subject_to_workload_rate",
                },
                scenarios_snapshot=[item.model_dump(mode="json") for item in scenarios],
            )
            self.session.add(snapshot)
            await self.session.commit()
            await self.session.refresh(snapshot)
            forecast_id = snapshot.id

        return ExecutionSLAForecastResponse(
            forecast_id=forecast_id,
            model_version=MODEL_VERSION,
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            remaining_actions=remaining_actions,
            deadline_days=deadline_days,
            required_daily_rate=required_daily_rate,
            deadline_at=deadline_at,
            target_sla=target_sla,
            lookback_days=lookback_days,
            simulations=effective_simulations,
            evidence_quality=quality,
            total_exposure_days=total_exposure,
            total_hard_failure_days=total_hard,
            current_reserve_percentage=current_reserve,
            current_scenario=current_scenario,
            recommended_scenario=recommended,
            status=status,
            warnings=warnings,
            accounts=account_rows,
            scenarios=scenarios,
        )

    async def history(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ExecutionSLAForecastHistoryItem]:
        stmt = select(ExecutionSLAForecastSnapshot).where(ExecutionSLAForecastSnapshot.owner_id == owner_id)
        if campaign_id is not None:
            stmt = stmt.where(ExecutionSLAForecastSnapshot.campaign_id == campaign_id)
        result = await self.session.execute(
            stmt.order_by(ExecutionSLAForecastSnapshot.created_at.desc()).limit(limit)
        )
        return [
            ExecutionSLAForecastHistoryItem(
                id=item.id,
                campaign_id=item.campaign_id,
                model_version=item.model_version,
                remaining_actions=item.remaining_actions,
                deadline_at=item.deadline_at,
                target_sla=item.target_sla,
                evidence_quality=item.evidence_quality,
                current_reserve_percentage=item.current_reserve_percentage,
                recommended_reserve_percentage=item.recommended_reserve_percentage,
                recommended_conservative_continuity_probability=item.recommended_conservative_continuity_probability,
                normal_daily_capacity=item.normal_daily_capacity,
                emergency_daily_capacity=item.emergency_daily_capacity,
                actual_completed_at=item.actual_completed_at,
                actual_met_sla=item.actual_met_sla,
                created_at=item.created_at,
            )
            for item in result.scalars().all()
        ]

    async def _historical_exposure(
        self,
        *,
        account_ids: list[UUID],
        lookback_days: int,
        now: datetime,
    ) -> dict[UUID, dict[str, int]]:
        cutoff = now - timedelta(days=lookback_days)
        hard_case = case((ActionJob.result_code.in_(HARD_COOLDOWN_CODES), 1), else_=0)
        result = await self.session.execute(
            select(
                ActionJob.account_id,
                func.date(ActionJob.started_at).label("execution_day"),
                func.max(hard_case).label("hard_failure"),
            )
            .where(
                ActionJob.account_id.in_(account_ids),
                ActionJob.started_at.is_not(None),
                ActionJob.started_at >= cutoff,
            )
            .group_by(ActionJob.account_id, func.date(ActionJob.started_at))
        )
        metrics: dict[UUID, dict[str, int]] = defaultdict(lambda: {"exposure_days": 0, "hard_failure_days": 0})
        for account_id, _execution_day, hard_failure in result.all():
            metrics[account_id]["exposure_days"] += 1
            metrics[account_id]["hard_failure_days"] += int(hard_failure or 0)
        return dict(metrics)
