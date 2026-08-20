from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.orchestration.execution_event_schemas import CampaignExecutionEventResponse
from app.features.orchestration.execution_events import CampaignExecutionEventService


router = APIRouter(prefix="/execution-events", tags=["orchestration", "execution-events"])


@router.get("", response_model=list[CampaignExecutionEventResponse])
async def list_execution_events(
    campaign_id: UUID | None = Query(default=None),
    event_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=200, ge=1, le=1000),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CampaignExecutionEventResponse]:
    items = await CampaignExecutionEventService(session).list_events(
        owner_id=user.id,
        campaign_id=campaign_id,
        event_type=event_type,
        limit=limit,
    )
    return [
        CampaignExecutionEventResponse(
            id=item.id,
            campaign_id=item.campaign_id,
            event_type=item.event_type,
            actor_type=item.actor_type,
            actor_user_id=item.actor_user_id,
            occurred_at=item.occurred_at,
            details=item.details,
            created_at=item.created_at,
        )
        for item in items
    ]
