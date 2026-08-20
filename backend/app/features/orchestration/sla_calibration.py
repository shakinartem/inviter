from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import HARD_COOLDOWN_CODES
from app.features.orchestration.continuity_labels import label_execution_continuity
from app.features.orchestration.execution_event_models import CampaignExecutionEvent
from app.features.orchestration.execution_events import CALIBRATION_CONFOUNDING_EVENTS
from app.features.orchestration.models import ActionJob
from app.features.orchestration.sla import MODEL_VERSION
from app.features.orchestration.sla_calibration_schemas import (
    SLACalibrationBucket,
    SLACalibrationResponse,
    SLAContinuityCalibrationBucket,
    SLAContinuityCalibrationResponse,
    SLAFinalizationResponse,
    SLALabelAuditItem,
)
from app.features.orchestration.sla_models import ExecutionSLAForecastSnapshot


CALIBRATION_BUCKETS = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.000001),
)


def _current_scenario(snapshot: ExecutionSLAForecastSnapshot) -> dict | None:
    scenarios = snapshot.scenarios_snapshot or []
    if not isinstance(scenarios, list) or not scenarios:
        return None
    reserve = float(snapshot.current_reserve_percentage or 0.0)
    usable = [item for item in scenarios if isinstance(item, dict)]
    if not usable:
        return None
    return min(usable, key=lambda item: abs(float(item.get("reserve_percentage", 0.0)) - reserve))


def current_workload_completion_probability(snapshot: ExecutionSLAForecastSnapshot) -> float | None:
    current = _current_scenario(snapshot)
    if current is None:
        return None
    value = current.get("modelled_workload_completion_probability")
    if value is None:
        return None
    return min(max(float(value), 0.0), 1.0)


def current_schedule_continuity_probability(snapshot: ExecutionSLAForecastSnapshot) -> float | None:
    current = _current_scenario(snapshot)
    if current is None:
        return None
    value = current.get("modelled_schedule_continuity_probability")
    if value is None:
        return None
    return min(max(float(value), 0.0), 1.0)


def calibration_metrics(predictions: list[float], outcomes: list[int]) -> dict:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        return {
            "mean_prediction": None,
            "observed_completion_rate": None,
            "calibration_bias": None,
            "brier_score": None,
            "expected_calibration_error": None,
            "buckets": [],
        }

    pairs = [(min(max(float(p), 0.0), 1.0), 1 if int(y) else 0) for p, y in zip(predictions, outcomes)]
    n = len(pairs)
    mean_prediction = sum(p for p, _ in pairs) / n
    observed = sum(y for _, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n

    buckets: list[dict] = []
    ece = 0.0
    for lower, upper in CALIBRATION_BUCKETS:
        selected = [(p, y) for p, y in pairs if lower <= p < upper]
        if not selected:
            buckets.append({
                "lower_bound": lower,
                "upper_bound": min(upper, 1.0),
                "samples": 0,
                "mean_prediction": None,
                "observed_completion_rate": None,
                "brier_score": None,
            })
            continue
        count = len(selected)
        bucket_prediction = sum(p for p, _ in selected) / count
        bucket_observed = sum(y for _, y in selected) / count
        bucket_brier = sum((p - y) ** 2 for p, y in selected) / count
        ece += (count / n) * abs(bucket_prediction - bucket_observed)
        buckets.append({
            "lower_bound": lower,
            "upper_bound": min(upper, 1.0),
            "samples": count,
            "mean_prediction": round(bucket_prediction, 4),
            "observed_completion_rate": round(bucket_observed, 4),
            "brier_score": round(bucket_brier, 4),
        })

    return {
        "mean_prediction": round(mean_prediction, 4),
        "observed_completion_rate": round(observed, 4),
        "calibration_bias": round(mean_prediction - observed, 4),
        "brier_score": round(brier, 4),
        "expected_calibration_error": round(ece, 4),
        "buckets": buckets,
    }


class ExecutionSLACalibrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def finalize_mature_forecasts(
        self,
        *,
        owner_id: UUID | None = None,
        limit: int = 100,
        now: datetime | None = None,
    ) -> SLAFinalizationResponse:
        now = now or datetime.now(timezone.utc)
        clauses = [
            ExecutionSLAForecastSnapshot.deadline_at <= now,
            ExecutionSLAForecastSnapshot.label_status == "pending",
        ]
        if owner_id is not None:
            clauses.append(ExecutionSLAForecastSnapshot.owner_id == owner_id)
        result = await self.session.execute(
            select(ExecutionSLAForecastSnapshot)
            .where(*clauses)
            .order_by(ExecutionSLAForecastSnapshot.deadline_at.asc())
            .with_for_update(skip_locked=True)
            .limit(max(1, min(int(limit), 1000)))
        )
        snapshots = list(result.scalars().all())
        labeled = 0
        ineligible = 0
        intervened = 0

        for snapshot in snapshots:
            forecast_created_at = self._aware(snapshot.created_at)
            deadline_at = self._aware(snapshot.deadline_at)

            # Reconstruct only the queue that already existed at prediction time.
            # Jobs created after the forecast must never rescue any old label.
            outstanding_at_forecast = int((await self.session.execute(
                select(func.count(ActionJob.id)).where(
                    ActionJob.campaign_id == snapshot.campaign_id,
                    ActionJob.owner_id == snapshot.owner_id,
                    ActionJob.created_at <= forecast_created_at,
                    or_(ActionJob.finished_at.is_(None), ActionJob.finished_at > forecast_created_at),
                )
            )).scalar() or 0)
            queue_eligible = outstanding_at_forecast >= int(snapshot.remaining_actions)

            success_clauses = [
                ActionJob.campaign_id == snapshot.campaign_id,
                ActionJob.owner_id == snapshot.owner_id,
                ActionJob.created_at <= forecast_created_at,
                ActionJob.status == "success",
                ActionJob.finished_at.is_not(None),
                ActionJob.finished_at > forecast_created_at,
                ActionJob.finished_at <= deadline_at,
            ]
            success_times = list((await self.session.execute(
                select(ActionJob.finished_at)
                .where(*success_clauses)
                .order_by(ActionJob.finished_at.asc())
            )).scalars().all())
            success_times = [self._aware(item) for item in success_times if item is not None]
            actual_successes = len(success_times)

            hard_days = int((await self.session.execute(
                select(func.count(func.distinct(func.date(ActionJob.started_at)))).where(
                    ActionJob.campaign_id == snapshot.campaign_id,
                    ActionJob.owner_id == snapshot.owner_id,
                    ActionJob.created_at <= forecast_created_at,
                    ActionJob.started_at.is_not(None),
                    ActionJob.started_at > forecast_created_at,
                    ActionJob.started_at <= deadline_at,
                    ActionJob.result_code.in_(HARD_COOLDOWN_CODES),
                )
            )).scalar() or 0)

            intervention_result = await self.session.execute(
                select(CampaignExecutionEvent)
                .where(
                    CampaignExecutionEvent.owner_id == snapshot.owner_id,
                    CampaignExecutionEvent.campaign_id == snapshot.campaign_id,
                    CampaignExecutionEvent.event_type.in_(CALIBRATION_CONFOUNDING_EVENTS),
                    CampaignExecutionEvent.occurred_at > forecast_created_at,
                    CampaignExecutionEvent.occurred_at <= deadline_at,
                )
                .order_by(CampaignExecutionEvent.occurred_at.asc())
            )
            interventions = list(intervention_result.scalars().all())

            snapshot.queue_eligible_at_forecast = queue_eligible
            snapshot.actual_successful_actions = actual_successes
            snapshot.actual_hard_failure_days = hard_days
            snapshot.label_finalized_at = now

            if not queue_eligible:
                snapshot.label_status = "ineligible_queue"
                snapshot.actual_met_sla = None
                snapshot.actual_completed_at = None
                snapshot.actual_met_continuity = None
                snapshot.actual_continuity_rate = None
                snapshot.continuity_windows_total = None
                snapshot.continuity_windows_met = None
                snapshot.continuity_label_notes = {
                    "reason": "forecast_requested_more_actions_than_reconstructible_queue",
                }
                snapshot.label_notes = {
                    "outstanding_jobs_at_forecast": outstanding_at_forecast,
                    "required_remaining_actions": int(snapshot.remaining_actions),
                    "reason": "forecast_requested_more_actions_than_reconstructible_queue",
                }
                ineligible += 1
                continue

            if interventions:
                snapshot.label_status = "intervened"
                snapshot.actual_met_sla = None
                snapshot.actual_completed_at = None
                snapshot.actual_met_continuity = None
                snapshot.actual_continuity_rate = None
                snapshot.continuity_windows_total = None
                snapshot.continuity_windows_met = None
                snapshot.continuity_label_notes = {
                    "reason": "operator_intervention_during_forecast_window",
                }
                snapshot.label_notes = {
                    "outstanding_jobs_at_forecast": outstanding_at_forecast,
                    "required_remaining_actions": int(snapshot.remaining_actions),
                    "reason": "operator_intervention_during_forecast_window",
                    "events": [
                        {
                            "event_type": event.event_type,
                            "occurred_at": self._aware(event.occurred_at).isoformat(),
                        }
                        for event in interventions[:50]
                    ],
                }
                intervened += 1
                continue

            met = actual_successes >= int(snapshot.remaining_actions)
            completed_at = (
                success_times[int(snapshot.remaining_actions) - 1]
                if met and int(snapshot.remaining_actions) > 0
                else None
            )
            continuity = label_execution_continuity(
                forecast_created_at=forecast_created_at,
                deadline_at=deadline_at,
                normal_daily_capacity=max(int(snapshot.normal_daily_capacity), 1),
                remaining_actions=int(snapshot.remaining_actions),
                successful_finished_at=success_times,
            )

            snapshot.actual_met_sla = met
            snapshot.actual_completed_at = completed_at
            snapshot.actual_met_continuity = continuity.met_continuity
            snapshot.actual_continuity_rate = continuity.continuity_rate
            snapshot.continuity_windows_total = continuity.windows_total
            snapshot.continuity_windows_met = continuity.windows_met
            snapshot.continuity_label_notes = {
                "label_semantics": "forecast_relative_24h_normal_rate_continuity",
                "prediction_time_jobs_only": True,
                "operator_intervention_free": True,
                "remaining_actions_at_deadline": continuity.remaining_actions_at_deadline,
                "windows": [
                    {
                        "index": item.index,
                        "start_at": item.start_at.isoformat(),
                        "end_at": item.end_at.isoformat(),
                        "required_actions": item.required_actions,
                        "successful_actions": item.successful_actions,
                        "met": item.met,
                    }
                    for item in continuity.windows
                ],
            }
            snapshot.label_status = "labeled"
            snapshot.label_notes = {
                "outstanding_jobs_at_forecast": outstanding_at_forecast,
                "required_remaining_actions": int(snapshot.remaining_actions),
                "label_semantics": "fixed_workload_completion_by_deadline",
                "prediction_time_jobs_only": True,
                "operator_intervention_free": True,
                "continuity_label_available": True,
            }
            labeled += 1

        await self.session.commit()

        remaining_clauses = [
            ExecutionSLAForecastSnapshot.deadline_at <= now,
            ExecutionSLAForecastSnapshot.label_status == "pending",
        ]
        if owner_id is not None:
            remaining_clauses.append(ExecutionSLAForecastSnapshot.owner_id == owner_id)
        still_pending = int((await self.session.execute(
            select(func.count(ExecutionSLAForecastSnapshot.id)).where(*remaining_clauses)
        )).scalar() or 0)

        return SLAFinalizationResponse(
            examined=len(snapshots),
            labeled=labeled,
            ineligible_queue=ineligible,
            intervened=intervened,
            still_pending=still_pending,
        )

    async def calibration(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        model_version: str = MODEL_VERSION,
        limit: int = 5000,
    ) -> SLACalibrationResponse:
        rows = await self._rows(
            owner_id=owner_id,
            campaign_id=campaign_id,
            model_version=model_version,
            limit=limit,
        )
        predictions: list[float] = []
        outcomes: list[int] = []
        ineligible, intervened, pending_mature = self._exclusion_counts(rows)
        for row in rows:
            if row.label_status != "labeled" or row.actual_met_sla is None:
                continue
            prediction = current_workload_completion_probability(row)
            if prediction is None:
                continue
            predictions.append(prediction)
            outcomes.append(1 if row.actual_met_sla else 0)

        metrics = calibration_metrics(predictions, outcomes)
        samples = len(predictions)
        status = self._calibration_status(samples, metrics["expected_calibration_error"])
        warnings = [
            "This endpoint evaluates fixed-workload completion probability for the reserve active at forecast time.",
            "Schedule continuity is a separate factual target exposed by /execution-sla/continuity-calibration.",
            "Forecasts with operator start/pause/stop/config intervention inside the prediction window are excluded from scoring.",
        ]
        warnings.extend(self._sample_warnings(samples, ineligible, intervened, pending_mature))

        return SLACalibrationResponse(
            model_version=model_version,
            campaign_id=campaign_id,
            labeled_samples=samples,
            ineligible_samples=ineligible,
            intervened_samples=intervened,
            pending_mature_samples=pending_mature,
            mean_prediction=metrics["mean_prediction"],
            observed_completion_rate=metrics["observed_completion_rate"],
            calibration_bias=metrics["calibration_bias"],
            brier_score=metrics["brier_score"],
            expected_calibration_error=metrics["expected_calibration_error"],
            status=status,
            warnings=warnings,
            buckets=[SLACalibrationBucket(**item) for item in metrics["buckets"]],
        )

    async def continuity_calibration(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        model_version: str = MODEL_VERSION,
        limit: int = 5000,
    ) -> SLAContinuityCalibrationResponse:
        rows = await self._rows(
            owner_id=owner_id,
            campaign_id=campaign_id,
            model_version=model_version,
            limit=limit,
        )
        predictions: list[float] = []
        outcomes: list[int] = []
        ineligible, intervened, pending_mature = self._exclusion_counts(rows)
        for row in rows:
            if row.label_status != "labeled" or row.actual_met_continuity is None:
                continue
            prediction = current_schedule_continuity_probability(row)
            if prediction is None:
                continue
            predictions.append(prediction)
            outcomes.append(1 if row.actual_met_continuity else 0)

        metrics = calibration_metrics(predictions, outcomes)
        samples = len(predictions)
        status = self._calibration_status(samples, metrics["expected_calibration_error"])
        warnings = [
            "Continuity is labeled over forecast-relative 24h windows, not server-calendar days.",
            "Each window must deliver the committed normal rate capped by remaining workload; later catch-up never erases an earlier missed window.",
            "Only prediction-time jobs and intervention-free forecast windows enter continuity calibration.",
        ]
        warnings.extend(self._sample_warnings(samples, ineligible, intervened, pending_mature))
        buckets = [
            SLAContinuityCalibrationBucket(
                lower_bound=item["lower_bound"],
                upper_bound=item["upper_bound"],
                samples=item["samples"],
                mean_prediction=item["mean_prediction"],
                observed_continuity_rate=item["observed_completion_rate"],
                brier_score=item["brier_score"],
            )
            for item in metrics["buckets"]
        ]
        return SLAContinuityCalibrationResponse(
            model_version=model_version,
            campaign_id=campaign_id,
            labeled_samples=samples,
            ineligible_samples=ineligible,
            intervened_samples=intervened,
            pending_mature_samples=pending_mature,
            mean_prediction=metrics["mean_prediction"],
            observed_continuity_rate=metrics["observed_completion_rate"],
            calibration_bias=metrics["calibration_bias"],
            brier_score=metrics["brier_score"],
            expected_calibration_error=metrics["expected_calibration_error"],
            status=status,
            warnings=warnings,
            buckets=buckets,
        )

    async def label_audit(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        limit: int = 100,
    ) -> list[SLALabelAuditItem]:
        stmt = select(ExecutionSLAForecastSnapshot).where(ExecutionSLAForecastSnapshot.owner_id == owner_id)
        if campaign_id is not None:
            stmt = stmt.where(ExecutionSLAForecastSnapshot.campaign_id == campaign_id)
        result = await self.session.execute(
            stmt.order_by(ExecutionSLAForecastSnapshot.created_at.desc()).limit(limit)
        )
        return [
            SLALabelAuditItem(
                id=row.id,
                campaign_id=row.campaign_id,
                remaining_actions=row.remaining_actions,
                forecast_created_at=row.created_at,
                deadline_at=row.deadline_at,
                predicted_completion_probability=current_workload_completion_probability(row),
                predicted_continuity_probability=current_schedule_continuity_probability(row),
                label_status=row.label_status,
                queue_eligible_at_forecast=row.queue_eligible_at_forecast,
                actual_successful_actions=row.actual_successful_actions,
                actual_hard_failure_days=row.actual_hard_failure_days,
                actual_met_sla=row.actual_met_sla,
                actual_met_continuity=row.actual_met_continuity,
                actual_continuity_rate=row.actual_continuity_rate,
                continuity_windows_total=row.continuity_windows_total,
                continuity_windows_met=row.continuity_windows_met,
                actual_completed_at=row.actual_completed_at,
                label_finalized_at=row.label_finalized_at,
            )
            for row in result.scalars().all()
        ]

    async def _rows(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None,
        model_version: str,
        limit: int,
    ) -> list[ExecutionSLAForecastSnapshot]:
        clauses = [
            ExecutionSLAForecastSnapshot.owner_id == owner_id,
            ExecutionSLAForecastSnapshot.model_version == model_version,
        ]
        if campaign_id is not None:
            clauses.append(ExecutionSLAForecastSnapshot.campaign_id == campaign_id)
        result = await self.session.execute(
            select(ExecutionSLAForecastSnapshot)
            .where(*clauses)
            .order_by(ExecutionSLAForecastSnapshot.created_at.desc())
            .limit(max(1, min(int(limit), 10000)))
        )
        return list(result.scalars().all())

    def _exclusion_counts(self, rows: list[ExecutionSLAForecastSnapshot]) -> tuple[int, int, int]:
        ineligible = sum(1 for row in rows if row.label_status == "ineligible_queue")
        intervened = sum(1 for row in rows if row.label_status == "intervened")
        now = datetime.now(timezone.utc)
        pending_mature = sum(
            1
            for row in rows
            if row.label_status not in {"labeled", "ineligible_queue", "intervened"}
            and self._aware(row.deadline_at) <= now
        )
        return ineligible, intervened, pending_mature

    @staticmethod
    def _calibration_status(samples: int, ece: float | None) -> str:
        if samples < 20:
            return "insufficient"
        if samples < 100:
            return "developing"
        if ece is not None and ece <= 0.10:
            return "usable"
        return "miscalibrated"

    @staticmethod
    def _sample_warnings(samples: int, ineligible: int, intervened: int, pending_mature: int) -> list[str]:
        warnings: list[str] = []
        if samples < 20:
            warnings.append("Fewer than 20 mature eligible forecasts: do not tune probability models from these metrics yet.")
        if ineligible:
            warnings.append(f"{ineligible} forecast(s) excluded because the prediction-time queue was smaller than remaining_actions.")
        if intervened:
            warnings.append(f"{intervened} forecast(s) excluded because operator intervention changed execution during the forecast window.")
        if pending_mature:
            warnings.append(f"{pending_mature} mature forecast(s) still need label finalization.")
        return warnings

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
