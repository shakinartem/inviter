from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.models import ActionJob
from app.features.orchestration.preflight_learning_schemas import (
    PreflightDecisionFinalizationResponse,
    PreflightDecisionHistoryItem,
    PreflightDecisionPerformanceResponse,
    PreflightDecisionPerformanceRow,
)
from app.features.orchestration.preflight_models import CampaignPreflightDecision
from app.features.orchestration.preflight_schemas import CampaignPreflightResponse
from app.features.orchestration.schemas import CampaignPlanResponse


PREFLIGHT_POLICY_VERSION = "campaign-preflight-v1"


class CampaignPreflightLearningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_launch(
        self,
        *,
        owner_id: UUID,
        preflight: CampaignPreflightResponse,
        plan: CampaignPlanResponse,
        tracked_job_ids: list[UUID],
        launched_at: datetime,
    ) -> CampaignPreflightDecision:
        tracked = list(dict.fromkeys(tracked_job_ids))
        label_status = "pending" if tracked else "ineligible_no_new_jobs"
        snapshot = CampaignPreflightDecision(
            owner_id=owner_id,
            campaign_id=preflight.campaign_id,
            policy_version=PREFLIGHT_POLICY_VERSION,
            decision=preflight.decision,
            action_budget_requested=preflight.action_budget_requested,
            action_budget_executable=preflight.action_budget_executable,
            planned_jobs=int(plan.planned),
            deadline_days=preflight.deadline_days,
            deadline_at=launched_at + timedelta(days=preflight.deadline_days),
            required_daily_rate=preflight.required_daily_rate,
            platform=preflight.platform,
            destination_ready=preflight.destination_ready,
            frozen_cohort_size=preflight.frozen_cohort_size,
            eligible_candidate_pool=preflight.eligible_candidate_pool,
            required_candidate_pool=preflight.required_candidate_pool,
            holdout_percentage=preflight.holdout_percentage,
            eligible_accounts=preflight.eligible_accounts,
            quarantined_accounts=preflight.quarantined_accounts,
            normal_daily_capacity=preflight.normal_daily_capacity,
            emergency_daily_capacity=preflight.emergency_daily_capacity,
            reserved_failover_headroom=preflight.reserved_failover_headroom,
            n_minus_one_surviving_capacity=preflight.n_minus_one_surviving_capacity,
            n_minus_one_covers_required_rate=preflight.n_minus_one_covers_required_rate,
            model_health_status=preflight.model_health_status,
            active_calibrator_version=preflight.active_calibrator_version,
            account_ids_snapshot=[str(item) for item in preflight.recommended_account_ids],
            checks_snapshot=[item.model_dump(mode="json") for item in preflight.checks],
            warnings_snapshot=list(preflight.warnings),
            plan_snapshot=plan.model_dump(mode="json"),
            tracked_job_ids=[str(item) for item in tracked],
            launched_at=launched_at,
            label_status=label_status,
            label_notes=(
                None
                if tracked
                else {
                    "reason": "launch_created_no_new_action_jobs",
                    "label_semantics": "new_action_jobs_success_by_preflight_deadline",
                }
            ),
        )
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def finalize_mature(
        self,
        *,
        owner_id: UUID | None = None,
        limit: int = 250,
        now: datetime | None = None,
    ) -> PreflightDecisionFinalizationResponse:
        now = now or datetime.now(timezone.utc)
        clauses = [
            CampaignPreflightDecision.label_status == "pending",
            CampaignPreflightDecision.deadline_at <= now,
        ]
        if owner_id is not None:
            clauses.append(CampaignPreflightDecision.owner_id == owner_id)
        result = await self.session.execute(
            select(CampaignPreflightDecision)
            .where(*clauses)
            .order_by(CampaignPreflightDecision.deadline_at.asc())
            .with_for_update(skip_locked=True)
            .limit(max(1, min(int(limit), 1000)))
        )
        snapshots = list(result.scalars().all())
        labeled = 0
        ineligible = 0

        for snapshot in snapshots:
            tracked_ids: list[UUID] = []
            for value in snapshot.tracked_job_ids or []:
                try:
                    tracked_ids.append(UUID(str(value)))
                except (TypeError, ValueError):
                    continue
            if not tracked_ids:
                snapshot.label_status = "ineligible_no_tracked_jobs"
                snapshot.label_finalized_at = now
                snapshot.label_notes = {"reason": "tracked_job_ids_missing_or_invalid"}
                ineligible += 1
                continue

            jobs = list((await self.session.execute(
                select(ActionJob).where(
                    ActionJob.owner_id == snapshot.owner_id,
                    ActionJob.campaign_id == snapshot.campaign_id,
                    ActionJob.id.in_(tracked_ids),
                )
            )).scalars().all())
            deadline = self._aware(snapshot.deadline_at)
            success = 0
            failed = 0
            cancelled = 0
            late_success = 0
            for job in jobs:
                finished = self._aware(job.finished_at) if job.finished_at is not None else None
                if job.status == "success" and finished is not None:
                    if finished <= deadline:
                        success += 1
                    else:
                        late_success += 1
                elif job.status == "failed" and finished is not None and finished <= deadline:
                    failed += 1
                elif job.status == "cancelled" and finished is not None and finished <= deadline:
                    cancelled += 1

            denominator = len(tracked_ids)
            unresolved_at_deadline = max(denominator - success - failed - cancelled, 0)
            snapshot.actual_successful_jobs = success
            snapshot.actual_failed_jobs = failed
            snapshot.actual_cancelled_jobs = cancelled
            snapshot.actual_completion_rate = round(success / denominator, 6) if denominator else None
            snapshot.actual_met_execution_plan = success >= denominator and denominator > 0
            snapshot.label_status = "labeled"
            snapshot.label_finalized_at = now
            snapshot.label_notes = {
                "label_semantics": "new_action_jobs_success_by_preflight_deadline",
                "tracked_jobs": denominator,
                "found_jobs": len(jobs),
                "unresolved_at_deadline": unresolved_at_deadline,
                "late_successes_not_counted": late_success,
                "deadline_at": deadline.isoformat(),
            }
            labeled += 1

        await self.session.commit()
        remaining_clauses = [
            CampaignPreflightDecision.label_status == "pending",
            CampaignPreflightDecision.deadline_at <= now,
        ]
        if owner_id is not None:
            remaining_clauses.append(CampaignPreflightDecision.owner_id == owner_id)
        still_pending = int((await self.session.execute(
            select(func.count(CampaignPreflightDecision.id)).where(*remaining_clauses)
        )).scalar() or 0)
        return PreflightDecisionFinalizationResponse(
            examined=len(snapshots),
            labeled=labeled,
            ineligible=ineligible,
            still_pending=still_pending,
        )

    async def history(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        limit: int = 100,
    ) -> list[PreflightDecisionHistoryItem]:
        stmt = select(CampaignPreflightDecision).where(CampaignPreflightDecision.owner_id == owner_id)
        if campaign_id is not None:
            stmt = stmt.where(CampaignPreflightDecision.campaign_id == campaign_id)
        rows = list((await self.session.execute(
            stmt.order_by(CampaignPreflightDecision.created_at.desc()).limit(max(1, min(int(limit), 500)))
        )).scalars().all())
        return [self._history_item(row) for row in rows]

    async def performance(
        self,
        *,
        owner_id: UUID,
        policy_version: str = PREFLIGHT_POLICY_VERSION,
        limit: int = 10000,
    ) -> PreflightDecisionPerformanceResponse:
        rows = list((await self.session.execute(
            select(CampaignPreflightDecision)
            .where(
                CampaignPreflightDecision.owner_id == owner_id,
                CampaignPreflightDecision.policy_version == policy_version,
            )
            .order_by(CampaignPreflightDecision.created_at.desc())
            .limit(max(1, min(int(limit), 10000)))
        )).scalars().all())
        labeled_rows = [row for row in rows if row.label_status == "labeled" and row.actual_completion_rate is not None]
        groups: dict[str, list[CampaignPreflightDecision]] = defaultdict(list)
        for row in labeled_rows:
            groups[row.decision].append(row)

        by_decision: list[PreflightDecisionPerformanceRow] = []
        for decision in ("go", "go_with_guards", "block"):
            items = groups.get(decision, [])
            if not items:
                continue
            count = len(items)
            by_decision.append(
                PreflightDecisionPerformanceRow(
                    decision=decision,
                    labeled_launches=count,
                    mean_completion_rate=round(sum(float(item.actual_completion_rate or 0.0) for item in items) / count, 4),
                    plan_success_rate=round(sum(1 for item in items if item.actual_met_execution_plan) / count, 4),
                    mean_normal_daily_capacity=round(sum(item.normal_daily_capacity for item in items) / count, 2),
                    n_minus_one_coverage_rate=round(sum(1 for item in items if item.n_minus_one_covers_required_rate) / count, 4),
                )
            )

        ineligible = sum(1 for row in rows if row.label_status.startswith("ineligible"))
        now = datetime.now(timezone.utc)
        pending_mature = sum(
            1 for row in rows if row.label_status == "pending" and self._aware(row.deadline_at) <= now
        )
        sample_count = len(labeled_rows)
        status = "insufficient" if sample_count < 20 else ("developing" if sample_count < 100 else "usable")
        warnings = [
            "Performance is observational launch-policy evidence, not a causal estimate of GO vs WARN treatment effect.",
            "Only new ActionJobs created by the preflight launch are labeled; resume launches with no new jobs are excluded.",
        ]
        if sample_count < 20:
            warnings.append("Fewer than 20 labeled launches: do not tune preflight thresholds from these aggregates yet.")
        if pending_mature:
            warnings.append(f"{pending_mature} mature launch snapshot(s) still require finalization.")
        return PreflightDecisionPerformanceResponse(
            policy_version=policy_version,
            labeled_launches=sample_count,
            ineligible_launches=ineligible,
            pending_mature_launches=pending_mature,
            status=status,
            warnings=warnings,
            by_decision=by_decision,
        )

    @staticmethod
    def _history_item(row: CampaignPreflightDecision) -> PreflightDecisionHistoryItem:
        return PreflightDecisionHistoryItem(
            id=row.id,
            campaign_id=row.campaign_id,
            policy_version=row.policy_version,
            decision=row.decision,
            action_budget_requested=row.action_budget_requested,
            action_budget_executable=row.action_budget_executable,
            planned_jobs=row.planned_jobs,
            deadline_at=row.deadline_at,
            required_daily_rate=row.required_daily_rate,
            normal_daily_capacity=row.normal_daily_capacity,
            emergency_daily_capacity=row.emergency_daily_capacity,
            n_minus_one_covers_required_rate=row.n_minus_one_covers_required_rate,
            model_health_status=row.model_health_status,
            active_calibrator_version=row.active_calibrator_version,
            tracked_jobs=len(row.tracked_job_ids or []),
            label_status=row.label_status,
            actual_successful_jobs=row.actual_successful_jobs,
            actual_failed_jobs=row.actual_failed_jobs,
            actual_cancelled_jobs=row.actual_cancelled_jobs,
            actual_completion_rate=row.actual_completion_rate,
            actual_met_execution_plan=row.actual_met_execution_plan,
            launched_at=row.launched_at,
            label_finalized_at=row.label_finalized_at,
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
