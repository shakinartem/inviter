from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.experiments.evidence_health import CausalEvidenceHealthService
from app.features.experiments.evidence_health_schemas import EvidenceHealthRequest, EvidenceHealthResponse


router = APIRouter(prefix="/experiments", tags=["experiments", "evidence-health"])


@router.post("/evidence-health", response_model=EvidenceHealthResponse)
async def causal_evidence_health(
    payload: EvidenceHealthRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
) -> EvidenceHealthResponse:
    try:
        result = await CausalEvidenceHealthService(session).analyze(
            owner_id=user.id,
            payload=payload,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EvidenceHealthResponse(**result)
