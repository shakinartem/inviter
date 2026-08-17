from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebhookSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    allowed_stages: list[Literal["engagement", "business"]] = Field(default_factory=lambda: ["business"])
    allowed_event_types: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("allowed_event_types")
    @classmethod
    def normalize_event_types(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            item = value.strip().lower().replace(" ", "_")
            if item and item not in normalized:
                normalized.append(item)
        return normalized


class WebhookSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    allowed_stages: list[Literal["engagement", "business"]] | None = None
    allowed_event_types: list[str] | None = Field(default=None, max_length=100)

    @field_validator("allowed_event_types")
    @classmethod
    def normalize_event_types(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = []
        for value in values:
            item = value.strip().lower().replace(" ", "_")
            if item and item not in normalized:
                normalized.append(item)
        return normalized


class WebhookSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    allowed_stages: list[str]
    allowed_event_types: list[str]
    is_active: bool
    delivery_count: int
    accepted_count: int
    rejected_count: int
    last_received_at: datetime | None
    last_accepted_at: datetime | None
    last_failure_at: datetime | None
    last_error: str | None
    secret_rotated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebhookSourceSecretResponse(BaseModel):
    source: WebhookSourceResponse
    signing_secret: str
    webhook_path: str


class WebhookOutcomePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, max_length=128)
    action_job_id: UUID
    stage: Literal["engagement", "business"]
    event_type: str = Field(..., min_length=1, max_length=64)
    observed_at: datetime
    success: bool | None = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    value: float | None = None
    properties: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def normalize_event_type(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")


class WebhookIngestResponse(BaseModel):
    accepted: bool
    duplicate: bool
    outcome_event_id: UUID
