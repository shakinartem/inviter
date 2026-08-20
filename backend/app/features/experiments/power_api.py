from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.power import ExperimentPowerPlanner
from app.features.experiments.power_schemas import ExperimentPowerPlanResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "power-planning"])


@router.get("/power-plan", response_model=ExperimentPowerPlanResponse)
async def plan_experiment_power(
    segment_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    holdout_percentage: float = Query(default=10.0, gt=0.0, le=50.0),
    action_budget: int = Query(default=1000, ge=1, le=50000),
    target_lift_percentage_points: float = Query(default=2.0, gt=0.0, lt=100.0),
    alpha: float = Query(default=0.05, gt=0.0, lt=0.5),
    target_power: float = Query(default=0.8, gt=0.5, lt=1.0),
    baseline_rate_assumption: float | None = Query(default=None, gt=0.0, lt=100.0),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> ExperimentPowerPlanResponse:
    try:
        result = await ExperimentPowerPlanner(session).plan(
            owner_id=user.id,
            segment_id=segment_id,
            stage=stage,
            event_type=event_type,
            horizon_hours=horizon_hours,
            holdout_percentage=holdout_percentage,
            action_budget=action_budget,
            target_lift_percentage_points=target_lift_percentage_points,
            alpha=alpha,
            target_power=target_power,
            baseline_rate_assumption=baseline_rate_assumption,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ExperimentPowerPlanResponse(**result)
