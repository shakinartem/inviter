from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.orchestration.execution_event_models import CampaignExecutionEvent


CALIBRATION_CONFOUNDING_EVENTS = {
    "operator_start",
    "operator_pause",
    "operator_stop",
    "operator_config_change",
}


class CampaignExecutionEventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        event_type: str,
        actor_type: str,
        actor_user_id: UUID | None = None,
        occurred_at: datetime | None = None,
        details: dict | None = None,
        commit: bool = True,
    ) -> CampaignExecutionEvent:
        event = CampaignExecutionEvent(
            owner_id=owner_id,
            campaign_id=campaign_id,
            event_type=event_type[:64],
            actor_type=actor_type[:32],
            actor_user_id=actor_user_id,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            details=details,
        )
        self.session.add(event)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(event)
        return event

    async def list_events(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None = None,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[CampaignExecutionEvent]:
        stmt = select(CampaignExecutionEvent).where(CampaignExecutionEvent.owner_id == owner_id)
        if campaign_id is not None:
            stmt = stmt.where(CampaignExecutionEvent.campaign_id == campaign_id)
        if event_type:
            stmt = stmt.where(CampaignExecutionEvent.event_type == event_type)
        result = await self.session.execute(
            stmt.order_by(CampaignExecutionEvent.occurred_at.desc()).limit(max(1, min(int(limit), 1000)))
        )
        return list(result.scalars().all())

    async def confounding_events_between(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[CampaignExecutionEvent]:
        result = await self.session.execute(
            select(CampaignExecutionEvent)
            .where(
                CampaignExecutionEvent.owner_id == owner_id,
                CampaignExecutionEvent.campaign_id == campaign_id,
                CampaignExecutionEvent.event_type.in_(CALIBRATION_CONFOUNDING_EVENTS),
                CampaignExecutionEvent.occurred_at > start_at,
                CampaignExecutionEvent.occurred_at <= end_at,
            )
            .order_by(CampaignExecutionEvent.occurred_at.asc())
        )
        return list(result.scalars().all())
