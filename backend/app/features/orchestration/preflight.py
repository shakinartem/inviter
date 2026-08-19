from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import AccountCapacityRiskService
from app.features.accounts.models import Account
from app.features.connections.orchestration import ConnectionAwareOrchestrationService
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import connector_registry
from app.features.experiments.service import CampaignExperimentService
from app.features.inviter.models import InviteCampaign
from app.features.orchestration.destinations import CampaignDestinationService
from app.features.orchestration.preflight_math import recommend_preflight_budget
from app.features.orchestration.preflight_schemas import (
    CampaignPreflightAccount,
    CampaignPreflightCheck,
    CampaignPreflightResponse,
)
from app.features.orchestration.service import OrchestrationService
from app.features.orchestration.sla_live_monitoring import ExecutionSLALiveMonitoringService
from app.features.segments.models import CampaignAudienceSource


class CampaignExecutionPreflightService:
    """Produce a launch decision from the exact frozen campaign inputs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        register_default_connectors()

    async def evaluate(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        action_budget: int,
        deadline_days: int,
        min_activity_score: float,
        min_readiness_score: float,
        account_ids: list[UUID] | None,
    ) -> CampaignPreflightResponse:
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

        checks: list[CampaignPreflightCheck] = []
        warnings: list[str] = []

        self._add_check(
            checks,
            key="campaign_state",
            status="pass" if campaign.status in {"draft", "paused"} else "block",
            title="Campaign state",
            message=(
                f"Campaign is {campaign.status} and can be launched."
                if campaign.status in {"draft", "paused"}
                else f"Campaign status {campaign.status} is not a launchable preflight state."
            ),
            blocking=campaign.status not in {"draft", "paused"},
        )

        destination = await CampaignDestinationService(self.session).get_for_campaign(
            owner_id=owner_id,
            campaign_id=campaign_id,
        )
        destination_ready = False
        platform: str | None = None
        if destination is None:
            self._add_check(
                checks,
                key="destination",
                status="block",
                title="Destination",
                message="Campaign has no canonical destination.",
                blocking=True,
            )
        else:
            platform = destination.platform
            try:
                connector = connector_registry.get(destination.platform)
                direct_invite = bool(connector.capabilities.direct_invite)
            except Exception:
                direct_invite = False
            destination_ready = destination.platform == "telegram" and direct_invite
            self._add_check(
                checks,
                key="destination",
                status="pass" if destination_ready else "block",
                title="Destination",
                message=(
                    f"{destination.title or destination.external_id} is resolvable through {destination.platform}."
                    if destination_ready
                    else f"Direct invite is not executable for destination platform {destination.platform}."
                ),
                blocking=not destination_ready,
                details={"platform": destination.platform, "community_type": destination.community_type},
            )

        source = (
            await self.session.execute(
                select(CampaignAudienceSource).where(
                    CampaignAudienceSource.owner_id == owner_id,
                    CampaignAudienceSource.campaign_id == campaign_id,
                )
            )
        ).scalar_one_or_none()
        frozen_cohort_size = int(source.member_count) if source is not None else 0
        if source is None:
            self._add_check(
                checks,
                key="frozen_opportunity",
                status="block",
                title="Frozen Opportunity",
                message="Campaign has no frozen Opportunity cohort. Recreate it from a materialized segment.",
                blocking=True,
            )
        else:
            self._add_check(
                checks,
                key="frozen_opportunity",
                status="pass" if frozen_cohort_size > 0 else "block",
                title="Frozen Opportunity",
                message=f"Frozen cohort contains {frozen_cohort_size} members.",
                blocking=frozen_cohort_size <= 0,
                details={"segment_id": str(source.segment_id), "frozen_at": source.frozen_at.isoformat()},
            )

        experiment_service = CampaignExperimentService(self.session)
        experiment = await experiment_service.get_for_campaign(owner_id=owner_id, campaign_id=campaign_id)
        holdout_percentage = float(experiment.holdout_percentage) if experiment is not None else 0.0
        immutable_budget_mismatch = bool(
            experiment is not None
            and experiment.status == "assigned"
            and experiment.action_budget is not None
            and int(experiment.action_budget) != int(action_budget)
        )
        if immutable_budget_mismatch:
            self._add_check(
                checks,
                key="experiment_budget",
                status="block",
                title="Causal experiment budget",
                message=f"Experiment budget is frozen at {experiment.action_budget}; requested preflight budget is {action_budget}.",
                blocking=True,
            )

        required_candidate_pool = experiment_service.required_pool_size(
            action_budget=action_budget,
            holdout_percentage=holdout_percentage,
        )
        candidate_service = ConnectionAwareOrchestrationService(self.session)
        candidates = await candidate_service._get_candidates(
            owner_id=owner_id,
            campaign=campaign,
            platform=platform or "telegram",
            min_activity_score=min_activity_score,
            min_readiness_score=min_readiness_score,
            limit=required_candidate_pool,
        ) if source is not None and platform == "telegram" else []
        eligible_candidate_pool = len(candidates)
        if experiment is None:
            estimated_treatment_candidates = min(eligible_candidate_pool, action_budget)
        else:
            holdout_count = experiment_service.holdout_count_for_pool(
                pool_size=eligible_candidate_pool,
                action_budget=action_budget,
                holdout_percentage=holdout_percentage,
                full_pool_available=eligible_candidate_pool >= required_candidate_pool,
            ) if eligible_candidate_pool else 0
            estimated_treatment_candidates = max(eligible_candidate_pool - holdout_count, 0)
        action_budget_executable = min(action_budget, estimated_treatment_candidates)

        if eligible_candidate_pool <= 0:
            cohort_status = "block"
            cohort_message = "No resolvable candidates remain after Opportunity and score filters."
            cohort_blocking = True
        elif action_budget_executable < action_budget:
            cohort_status = "warn"
            cohort_message = (
                f"Only {action_budget_executable} treatment actions are currently supportable from "
                f"{eligible_candidate_pool} eligible candidates; requested budget is {action_budget}."
            )
            cohort_blocking = False
        else:
            cohort_status = "pass"
            cohort_message = (
                f"Candidate pool supports {action_budget} treatment actions"
                + (f" plus {holdout_percentage:.1f}% causal holdout." if holdout_percentage > 0 else ".")
            )
            cohort_blocking = False
        self._add_check(
            checks,
            key="candidate_pool",
            status=cohort_status,
            title="Executable Opportunity",
            message=cohort_message,
            blocking=cohort_blocking,
            details={
                "eligible_candidate_pool": eligible_candidate_pool,
                "required_candidate_pool": required_candidate_pool,
                "holdout_percentage": holdout_percentage,
                "executable_treatment_actions": action_budget_executable,
            },
        )

        risk_assessments = await AccountCapacityRiskService(self.session).evaluate_pool(
            owner_id=owner_id,
            platform="telegram",
            campaign_daily_limit=max(int(campaign.daily_limit_per_account), 1),
            account_ids=account_ids,
            persist_snapshots=False,
        )
        eligible_assessments = [item for item in risk_assessments if item.eligible]
        quarantined_accounts = len(risk_assessments) - len(eligible_assessments)
        assessment_by_id = {item.account_id: item for item in eligible_assessments}

        accounts: list[Account] = []
        if assessment_by_id:
            accounts = list((await self.session.execute(
                select(Account)
                .where(
                    Account.owner_id == owner_id,
                    Account.id.in_(assessment_by_id.keys()),
                )
                .order_by(Account.health_score.desc(), Account.last_used_at.asc().nullsfirst())
            )).scalars().all())

        reserve_percentage = min(max(float(campaign.reserve_capacity_percentage or 0.0), 0.0), 50.0)
        now = datetime.now(timezone.utc)
        account_rows: list[CampaignPreflightAccount] = []
        emergency_caps: list[int] = []
        normal_caps: list[int] = []
        for account in accounts:
            assessment = assessment_by_id[account.id]
            warmup_limit = OrchestrationService._effective_daily_limit(account, campaign, now)
            emergency = max(min(int(assessment.suggested_daily_capacity), int(warmup_limit)), 1)
            normal = max(int(emergency * (1.0 - reserve_percentage / 100.0)), 1)
            normal = min(normal, emergency)
            emergency_caps.append(emergency)
            normal_caps.append(normal)
            account_rows.append(
                CampaignPreflightAccount(
                    account_id=account.id,
                    label=account.label,
                    health_score=float(assessment.health_score),
                    risk_score=float(assessment.risk_score),
                    emergency_daily_capacity=emergency,
                    normal_daily_capacity=normal,
                    queued_jobs=int(assessment.queued_jobs),
                    reasons=list(assessment.reasons),
                )
            )

        normal_total = sum(normal_caps)
        emergency_total = sum(emergency_caps)
        reserved_headroom = max(emergency_total - normal_total, 0)
        budget_recommendation = recommend_preflight_budget(
            requested_actions=action_budget,
            executable_actions=action_budget_executable,
            normal_daily_capacity=normal_total,
            deadline_days=deadline_days,
        )
        required_daily_rate = budget_recommendation.required_daily_rate
        estimated_days = budget_recommendation.estimated_completion_days
        max_emergency = max(emergency_caps, default=0)
        n_minus_one_surviving = max(emergency_total - max_emergency, 0)
        n_minus_one_covers = (
            len(emergency_caps) >= 2
            and required_daily_rate > 0
            and n_minus_one_surviving >= required_daily_rate
        )

        if not account_rows:
            self._add_check(
                checks,
                key="safe_capacity",
                status="block",
                title="Safe account capacity",
                message="No currently eligible Telegram accounts are available.",
                blocking=True,
            )
        else:
            capacity_ok = (
                action_budget_executable > 0
                and budget_recommendation.maximum_safe_action_budget >= action_budget_executable
            )
            if capacity_ok:
                capacity_message = (
                    f"Normal safe capacity is {normal_total}/day for the executable workload requirement of "
                    f"{required_daily_rate}/day."
                )
            else:
                deadline_hint = (
                    f" or extend the horizon to at least {budget_recommendation.recommended_deadline_days} days"
                    if budget_recommendation.recommended_deadline_days is not None
                    else ""
                )
                capacity_message = (
                    f"Only {budget_recommendation.maximum_safe_action_budget} of {action_budget_executable} executable actions "
                    f"fit inside {deadline_days} days at normal safe capacity. Reduce the budget to "
                    f"{budget_recommendation.recommended_action_budget}{deadline_hint}."
                )
            self._add_check(
                checks,
                key="safe_capacity",
                status="pass" if capacity_ok else "block",
                title="Safe account capacity",
                message=capacity_message,
                blocking=not capacity_ok,
                details={
                    "required_daily_rate": required_daily_rate,
                    "normal_daily_capacity": normal_total,
                    "emergency_daily_capacity": emergency_total,
                    "reserved_failover_headroom": reserved_headroom,
                    "reserve_capacity_percentage": reserve_percentage,
                    "maximum_safe_action_budget": budget_recommendation.maximum_safe_action_budget,
                    "recommended_action_budget": budget_recommendation.recommended_action_budget,
                    "recommended_deadline_days": budget_recommendation.recommended_deadline_days,
                },
            )

        if len(account_rows) < 2:
            n1_status = "warn"
            n1_message = "Account pool has a single point of failure; N-1 coverage is unavailable."
        elif n_minus_one_covers:
            n1_status = "pass"
            n1_message = f"After losing the largest account, {n_minus_one_surviving}/day still covers required {required_daily_rate}/day."
        else:
            n1_status = "warn"
            n1_message = f"Losing the largest account leaves {n_minus_one_surviving}/day, below required {required_daily_rate}/day."
        self._add_check(
            checks,
            key="n_minus_one",
            status=n1_status,
            title="N-1 execution resilience",
            message=n1_message,
            blocking=False,
        )

        total_backlog = sum(item.queued_jobs for item in account_rows)
        if total_backlog > emergency_total * 2 and emergency_total > 0:
            self._add_check(
                checks,
                key="existing_backlog",
                status="warn",
                title="Existing account backlog",
                message=f"Selected account pool already carries {total_backlog} queued jobs against {emergency_total}/day emergency capacity.",
                blocking=False,
            )

        model_health = await ExecutionSLALiveMonitoringService(self.session).evaluate(owner_id=owner_id)
        if model_health.status == "revalidation_required":
            self._add_check(
                checks,
                key="model_health",
                status="warn",
                title="Execution probability model",
                message="Active completion calibrator requires revalidation. Launch safety still uses raw conservative policy.",
                blocking=False,
            )
        else:
            self._add_check(
                checks,
                key="model_health",
                status="pass",
                title="Execution probability model",
                message=f"Point-probability model status: {model_health.status}.",
                blocking=False,
            )

        if quarantined_accounts:
            warnings.append(f"{quarantined_accounts} account(s) are currently excluded by account-risk policy.")
        if action_budget_executable < action_budget and action_budget_executable > 0:
            warnings.append(
                f"Frozen Opportunity supports {action_budget_executable} treatment actions versus {action_budget} requested."
            )
        if budget_recommendation.deadline_extension_needed:
            warnings.append(
                f"Current safe capacity needs at least {budget_recommendation.recommended_deadline_days} days for the executable workload."
            )
        if budget_recommendation.budget_reduction_needed:
            warnings.append(
                f"Maximum safe treatment budget for the current cohort/capacity/horizon is {budget_recommendation.recommended_action_budget}."
            )
        if reserve_percentage <= 0:
            warnings.append("Campaign has 0% explicit failover reserve; N-1 safety depends entirely on unused physical capacity.")

        has_block = any(item.blocking and item.status == "block" for item in checks)
        has_warn = any(item.status == "warn" for item in checks)
        decision = "block" if has_block else ("go_with_guards" if has_warn else "go")

        return CampaignPreflightResponse(
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            decision=decision,
            action_budget_requested=action_budget,
            action_budget_executable=action_budget_executable,
            maximum_safe_action_budget=budget_recommendation.maximum_safe_action_budget,
            recommended_action_budget=budget_recommendation.recommended_action_budget,
            budget_reduction_needed=budget_recommendation.budget_reduction_needed,
            deadline_days=deadline_days,
            recommended_deadline_days=budget_recommendation.recommended_deadline_days,
            deadline_extension_needed=budget_recommendation.deadline_extension_needed,
            required_daily_rate=required_daily_rate,
            platform=platform,
            destination_title=(destination.title if destination else None),
            destination_ready=destination_ready,
            frozen_cohort_size=frozen_cohort_size,
            eligible_candidate_pool=eligible_candidate_pool,
            required_candidate_pool=required_candidate_pool,
            holdout_percentage=holdout_percentage,
            estimated_treatment_candidates=estimated_treatment_candidates,
            eligible_accounts=len(account_rows),
            quarantined_accounts=quarantined_accounts,
            recommended_account_ids=[item.account_id for item in account_rows],
            normal_daily_capacity=normal_total,
            emergency_daily_capacity=emergency_total,
            reserved_failover_headroom=reserved_headroom,
            estimated_completion_days=estimated_days,
            n_minus_one_surviving_capacity=n_minus_one_surviving,
            n_minus_one_covers_required_rate=n_minus_one_covers,
            model_health_status=model_health.status,
            active_calibrator_version=model_health.active_calibrator_version,
            checks=checks,
            accounts=account_rows,
            warnings=warnings,
        )

    @staticmethod
    def _add_check(
        checks: list[CampaignPreflightCheck],
        *,
        key: str,
        status: str,
        title: str,
        message: str,
        blocking: bool,
        details: dict | None = None,
    ) -> None:
        checks.append(
            CampaignPreflightCheck(
                key=key,
                status=status,
                blocking=blocking,
                title=title,
                message=message,
                details=details,
            )
        )
