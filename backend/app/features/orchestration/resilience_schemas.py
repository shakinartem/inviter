from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ResilienceAccountResponse(BaseModel):
    account_id: UUID
    label: str
    health_score: float
    emergency_daily_capacity: int
    normal_daily_capacity: int
    reserved_headroom: int


class CampaignResilienceResponse(BaseModel):
    campaign_id: UUID
    campaign_title: str
    reserve_capacity_percentage: float
    campaign_accounts: int
    normal_daily_capacity: int
    emergency_daily_capacity: int
    reserved_failover_headroom: int
    worst_single_account_loss_capacity: int
    n_minus_one_surviving_capacity: int
    n_minus_one_margin: int
    n_minus_one_covered: bool
    resilience_ratio: float
    recommended_min_reserve_percentage: float | None
    status: str
    warnings: list[str]
    accounts: list[ResilienceAccountResponse]
