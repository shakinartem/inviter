from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.allocations.schemas import (
    CapacityAllocationAssignmentListResponse,
    CapacityAllocationAssignmentResponse,
    CapacityAllocationCreate,
    CapacityAllocationPlanResponse,
)
from app.features.allocations.service import CapacityAllocationService


router = APIRouter(prefix="/allocations", tags=["allocations", "causal-allocation"])


@router.post("/plans", response_model=CapacityAllocationPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_allocation_plan(
    payload: CapacityAllocationCreate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CapacityAllocationPlanResponse:
    try:
        plan = await CapacityAllocationService(session).create_plan(
            owner_id=user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CapacityAllocationPlanResponse.model_validate(plan)


@router.get("/plans", response_model=list[CapacityAllocationPlanResponse])
async def list_allocation_plans(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CapacityAllocationPlanResponse]:
    items, _total = await CapacityAllocationService(session).list_plans(
        owner_id=user.id,
        skip=skip,
        limit=limit,
    )
    return [CapacityAllocationPlanResponse.model_validate(item) for item in items]


@router.get("/plans/{plan_id}", response_model=CapacityAllocationPlanResponse)
async def get_allocation_plan(
    plan_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CapacityAllocationPlanResponse:
    plan = await CapacityAllocationService(session).get_plan(owner_id=user.id, plan_id=plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation plan not found")
    return CapacityAllocationPlanResponse.model_validate(plan)


@router.get(
    "/plans/{plan_id}/assignments",
    response_model=CapacityAllocationAssignmentListResponse,
)
async def list_allocation_assignments(
    plan_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    segment_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> CapacityAllocationAssignmentListResponse:
    try:
        items, total = await CapacityAllocationService(session).assignments(
            owner_id=user.id,
            plan_id=plan_id,
            segment_id=segment_id,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CapacityAllocationAssignmentListResponse(
        items=[CapacityAllocationAssignmentResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )
