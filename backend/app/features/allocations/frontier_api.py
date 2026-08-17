from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.allocations.frontier import CapacityEconomicsFrontierService
from app.features.allocations.frontier_schemas import CapacityFrontierRequest, CapacityFrontierResponse


router = APIRouter(prefix="/allocations", tags=["allocations", "capacity-economics"])


@router.post("/capacity-frontier", response_model=CapacityFrontierResponse)
async def capacity_frontier(
    payload: CapacityFrontierRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CapacityFrontierResponse:
    try:
        result = await CapacityEconomicsFrontierService(session).forecast(
            owner_id=user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CapacityFrontierResponse(**result)
