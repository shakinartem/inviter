from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(..., min_length=2, max_length=32)
    label: str = Field(..., min_length=1, max_length=120)
    auth_type: str = Field(default="token", min_length=2, max_length=32)
    external_account_id: str | None = Field(default=None, max_length=128)
    credentials: dict[str, Any] = Field(default_factory=dict)
    proxy_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None

    @field_validator("platform", "auth_type")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")


class ConnectionCredentialsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_type: str | None = Field(default=None, min_length=2, max_length=32)
    credentials: dict[str, Any]


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=120)
    external_account_id: str | None = Field(default=None, max_length=128)
    proxy_id: UUID | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    platform: str
    external_account_id: str | None
    label: str
    auth_type: str
    username: str | None
    first_name: str | None
    last_name: str | None
    status: str
    status_message: str | None
    is_active: bool
    capabilities: dict[str, bool] | None
    health_score: float
    proxy_id: UUID | None
    last_seen_at: datetime | None
    last_used_at: datetime | None
    last_checked_at: datetime | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="extra_data")
    notes: str | None
    has_credentials: bool = False
    connector_available: bool = False
    created_at: datetime
    updated_at: datetime


class ConnectionCheckResponse(BaseModel):
    account_id: UUID
    platform: str
    ok: bool
    connector_available: bool
    status: str
    external_account_id: str | None = None
    username: str | None = None
    error: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)


class PlatformConnectionStatus(BaseModel):
    platform: str
    connector_available: bool
    capabilities: dict[str, bool] = Field(default_factory=dict)
