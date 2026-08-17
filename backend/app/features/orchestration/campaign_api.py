from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.inviter.schemas import InviteCampaignResponse, InviteSettings
from app.features.orchestration.destinations import CampaignDestinationService
from app.features.segments.service import SegmentService


router = APIRouter(prefix="/orchestration/campaigns", tags=["orchestration"])


class CampaignCreateFromCommunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=160)
    target_community_id: UUID
    source_segment_id: UUID
    notes: str | None = Field(default=None, max_length=2000)
    settings: InviteSettings = Field(default_factory=InviteSettings)


@router.post("", response_model=InviteCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign_from_community(
    payload: CampaignCreateFromCommunityRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InviteCampaignResponse:
    destination_service = CampaignDestinationService(session)
    segment_service = SegmentService(session)
    try:
        segment = await segment_service.get(user.id, payload.source_segment_id)
        if segment is None:
            raise ValueError("Audience segment not found")

        campaign, destination = await destination_service.create_campaign_from_community(
            owner_id=user.id,
            title=payload.title,
            target_community_id=payload.target_community_id,
            source_type="parsed_list",  # legacy compatibility cache; canonical source is below
            settings=payload.settings.model_dump(),
            notes=payload.notes,
            commit=False,
        )
        if segment.platform != destination.platform:
            raise ValueError(
                f"Opportunity platform ({segment.platform}) must match destination platform ({destination.platform})"
            )
        if destination.platform != "telegram":
            raise ValueError(
                "Current direct-invite campaign action is Telegram-only; use a Telegram Opportunity and destination"
            )

        await segment_service.freeze_for_campaign(
            owner_id=user.id,
            segment_id=payload.source_segment_id,
            campaign_id=campaign.id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return InviteCampaignResponse.model_validate(campaign)
