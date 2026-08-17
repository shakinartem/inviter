from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_active_user
from app.features.intelligence.schemas import CommunityScoreRequest, CommunityScoreResponse
from app.features.intelligence.scoring import CommunityScoreInput, score_community


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post("/community-score", response_model=CommunityScoreResponse)
async def preview_community_score(
    payload: CommunityScoreRequest,
    _user=Depends(get_current_active_user),
) -> CommunityScoreResponse:
    result = score_community(CommunityScoreInput(**payload.model_dump()))
    return CommunityScoreResponse(**result.as_dict())
