from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.learning.feedback import FeedbackQueueService
from app.features.learning.schemas import (
    CalibrationResponse,
    FeedbackActionListResponse,
    FeedbackActionResponse,
    LearningOverviewResponse,
    ObservedOutcomeCreate,
    OutcomeEventListResponse,
    OutcomeEventResponse,
)
from app.features.learning.service import OutcomeLearningService


router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/outcomes", response_model=OutcomeEventResponse, status_code=status.HTTP_201_CREATED)
async def record_outcome(
    payload: ObservedOutcomeCreate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> OutcomeEventResponse:
    service = OutcomeLearningService(session)
    try:
        event = await service.record_observed_outcome(
            owner_id=user.id,
            action_job_id=payload.action_job_id,
            stage=payload.stage,
            event_type=payload.event_type,
            success=payload.success,
            source=payload.source,
            confidence=payload.confidence,
            value=payload.value,
            observed_at=payload.observed_at,
            external_event_id=payload.external_event_id,
            idempotency_key=payload.idempotency_key,
            properties=payload.properties,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OutcomeEventResponse.model_validate(event)


@router.get("/actions", response_model=FeedbackActionListResponse)
async def feedback_actions(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    campaign_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeedbackActionListResponse:
    items, total = await FeedbackQueueService(session).list_actions(
        owner_id=user.id,
        campaign_id=campaign_id,
        skip=skip,
        limit=limit,
    )
    return FeedbackActionListResponse(
        items=[FeedbackActionResponse(**item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/outcomes", response_model=OutcomeEventListResponse)
async def list_outcomes(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str | None = Query(default=None, max_length=32),
    event_type: str | None = Query(default=None, max_length=64),
    campaign_id: UUID | None = Query(default=None),
    audience_member_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> OutcomeEventListResponse:
    service = OutcomeLearningService(session)
    items, total = await service.list_outcomes(
        owner_id=user.id,
        stage=stage,
        event_type=event_type,
        campaign_id=campaign_id,
        audience_member_id=audience_member_id,
        skip=skip,
        limit=limit,
    )
    return OutcomeEventListResponse(
        items=[OutcomeEventResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/overview", response_model=LearningOverviewResponse)
async def learning_overview(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> LearningOverviewResponse:
    result = await OutcomeLearningService(session).overview(owner_id=user.id)
    return LearningOverviewResponse(**result)


@router.get("/calibration", response_model=CalibrationResponse)
async def calibration(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(transport|engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    bucket_size: int = Query(default=20, ge=10, le=50),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> CalibrationResponse:
    result = await OutcomeLearningService(session).calibration(
        owner_id=user.id,
        stage=stage,
        event_type=event_type,
        horizon_hours=horizon_hours,
        bucket_size=bucket_size,
        min_confidence=min_confidence,
    )
    return CalibrationResponse(**result)
