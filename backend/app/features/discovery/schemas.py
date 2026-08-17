from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlatformDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=200)
    account_id: UUID | None = None
    limit: int = Field(default=100, ge=1, le=200)
    chat_type: str | None = Field(default=None, max_length=32)
