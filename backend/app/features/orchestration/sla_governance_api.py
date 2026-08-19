from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.sla_governance import ExecutionSLAGovernanceService
from app.features.orchestration.sla_governance_schemas import (
    SLACalibratorResponse,
    SLACalibratorTrainRequest,
    SLACalibratorTrainResponse,
)


router = APIRouter(prefix="/execution-sla/calibrators", tags=["execution-sla", "model-governance"])


@router.get("", response_model=list[SLACalibratorResponse])
async def list_calibrators(
    base_model_version: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[SLACalibratorResponse]:
    return await ExecutionSLAGovernanceService(session).list_calibrators(
        owner_id=user.id,
        base_model_version=base_model_version,
        limit=limit,
    )


@router.post("/train", response_model=SLACalibratorTrainResponse)
async def train_calibrator(
    payload: SLACalibratorTrainRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLACalibratorTrainResponse:
    return await ExecutionSLAGovernanceService(session).train_candidate(
        owner_id=user.id,
        base_model_version=payload.base_model_version,
        min_samples=payload.min_samples,
        test_fraction=payload.test_fraction,
        prior_strength=payload.prior_strength,
    )


@router.post("/{calibrator_id}/activate", response_model=SLACalibratorResponse)
async def activate_calibrator(
    calibrator_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLACalibratorResponse:
    try:
        return await ExecutionSLAGovernanceService(session).activate(
            owner_id=user.id,
            calibrator_id=calibrator_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{calibrator_id}/retire", response_model=SLACalibratorResponse)
async def retire_calibrator(
    calibrator_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> SLACalibratorResponse:
    try:
        return await ExecutionSLAGovernanceService(session).retire(
            owner_id=user.id,
            calibrator_id=calibrator_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
