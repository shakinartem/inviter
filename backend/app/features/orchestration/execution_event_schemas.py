from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CampaignExecutionEventResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    event_type: str
    actor_type: str
    actor_user_id: UUID | None
    occurred_at: datetime
    details: dict | None
    created_at: datetime
