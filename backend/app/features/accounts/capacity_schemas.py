from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCapacityAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    label: str
    platform: str
    status: str
    health_score: float
    risk_score: float
    capacity_multiplier: float
    suggested_daily_capacity: int
    campaign_daily_limit: int
    attempts_24h: int
    successes_24h: int
    account_errors_24h: int
    target_errors_24h: int
    floodwaits_24h: int
    peer_floods_7d: int
    connector_errors_24h: int
    queued_jobs: int
    eligible: bool
    next_safe_at: datetime | None
    reasons: list[str]
    calculated_at: datetime


class AccountCapacityPoolResponse(BaseModel):
    platform: str
    campaign_daily_limit: int
    total_accounts: int
    eligible_accounts: int
    quarantined_accounts: int
    suggested_total_daily_capacity: int
    queued_jobs: int
    average_health_score: float
    assessments: list[AccountCapacityAssessmentResponse]


class AccountCapacityRefreshRequest(BaseModel):
    platform: str = Field(default="telegram", min_length=1, max_length=32)
    campaign_daily_limit: int = Field(default=30, ge=1, le=1000)
    persist_snapshots: bool = True


class AccountCapacityHistoryResponse(BaseModel):
    account_id: UUID
    items: list[dict]


class AccountRiskPolicyResponse(BaseModel):
    policy_version: Literal["account-risk-v1"] = "account-risk-v1"
    principle: str = "Risk engine may only reduce campaign capacity or pause an account; it never increases platform limits."
    account_level_codes: list[str]
    target_level_codes: list[str]
    destination_level_codes: list[str]
    hard_cooldown_codes: list[str]
