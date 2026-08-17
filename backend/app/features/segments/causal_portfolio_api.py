from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.segments.causal_portfolio import CausalOpportunityPortfolioService
from app.features.segments.causal_portfolio_schemas import CausalOpportunityPortfolioResponse


router = APIRouter(prefix="/segments", tags=["segments", "causal-portfolio"])


@router.get("/causal-portfolio/forecast", response_model=CausalOpportunityPortfolioResponse)
async def forecast_causal_opportunity_portfolio(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stage: str = Query(default="business", pattern="^(engagement|business)$"),
    event_type: str = Query(default="converted", min_length=1, max_length=64),
    horizon_hours: int = Query(default=168, ge=1, le=2160),
    action_budget: int = Query(default=1000, ge=1, le=50000),
    platform: str | None = Query(default="telegram", max_length=32),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> CausalOpportunityPortfolioResponse:
    try:
        result = await CausalOpportunityPortfolioService(session).forecast(
            owner_id=user.id,
            stage=stage,
            event_type=event_type,
            horizon_hours=horizon_hours,
            action_budget=action_budget,
            platform=platform,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CausalOpportunityPortfolioResponse(**result)
