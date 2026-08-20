from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.capacity import AccountCapacityRiskService
from app.features.accounts.models import Account
from app.features.inviter.models import InviteCampaign
from app.features.orchestration.models import ActionJob
from app.features.orchestration.resilience_schemas import (
    CampaignResilienceResponse,
    ResilienceAccountResponse,
)
from app.features.orchestration.service import OrchestrationService


@dataclass(frozen=True, slots=True)
class ResilienceSummary:
    normal_capacities: tuple[int, ...]
    normal_daily_capacity: int
    emergency_daily_capacity: int
    reserved_failover_headroom: int
    worst_single_account_loss_capacity: int
    n_minus_one_surviving_capacity: int
    n_minus_one_margin: int
    n_minus_one_covered: bool
    resilience_ratio: float
    recommended_min_reserve_percentage: float | None


def summarize_resilience_capacities(
    emergency_capacities: list[int] | tuple[int, ...],
    reserve_percentage: float,
) -> ResilienceSummary:
    """Pure N-1 capacity calculation used by API and regression tests."""
    reserve = min(max(float(reserve_percentage), 0.0), 50.0)
    emergency = tuple(max(int(value), 0) for value in emergency_capacities if int(value) > 0)
    normal = tuple(
        min(max(int(value * (1.0 - reserve / 100.0)), 1), value)
        for value in emergency
    )
    emergency_total = sum(emergency)
    normal_total = sum(normal)
    max_account = max(emergency, default=0)
    surviving = max(emergency_total - max_account, 0)
    margin = surviving - normal_total
    covered = len(emergency) >= 2 and normal_total > 0 and margin >= 0
    ratio = round(surviving / normal_total, 3) if normal_total > 0 else 0.0

    recommended: float | None = None
    if emergency_total > 0 and len(emergency) >= 2:
        recommended = min(float(ceil(100.0 * max_account / emergency_total)), 50.0)

    return ResilienceSummary(
        normal_capacities=normal,
        normal_daily_capacity=normal_total,
        emergency_daily_capacity=emergency_total,
        reserved_failover_headroom=max(emergency_total - normal_total, 0),
        worst_single_account_loss_capacity=max_account,
        n_minus_one_surviving_capacity=surviving,
        n_minus_one_margin=margin,
        n_minus_one_covered=covered,
        resilience_ratio=ratio,
        recommended_min_reserve_percentage=recommended,
    )


class CampaignResilienceService:
    """Evaluate whether a planned campaign can survive one account loss.

    Normal capacity respects the campaign's explicit reserve percentage. Emergency
    capacity uses the same risk/warmup ceilings without the reserve reduction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
    ) -> CampaignResilienceResponse:
        campaign = (
            await self.session.execute(
                select(InviteCampaign).where(
                    InviteCampaign.id == campaign_id,
                    InviteCampaign.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if campaign is None:
            raise ValueError("Campaign not found")

        pool_result = await self.session.execute(
            select(ActionJob.account_id)
            .where(
                ActionJob.owner_id == owner_id,
                ActionJob.campaign_id == campaign_id,
                ActionJob.platform == "telegram",
            )
            .distinct()
        )
        account_ids = list(pool_result.scalars().all())
        if not account_ids:
            return CampaignResilienceResponse(
                campaign_id=campaign.id,
                campaign_title=campaign.title,
                reserve_capacity_percentage=float(campaign.reserve_capacity_percentage or 0.0),
                campaign_accounts=0,
                normal_daily_capacity=0,
                emergency_daily_capacity=0,
                reserved_failover_headroom=0,
                worst_single_account_loss_capacity=0,
                n_minus_one_surviving_capacity=0,
                n_minus_one_margin=0,
                n_minus_one_covered=False,
                resilience_ratio=0.0,
                recommended_min_reserve_percentage=None,
                status="not_planned",
                warnings=["Campaign has no assigned account pool yet. Start/plan it before resilience analysis."],
                accounts=[],
            )

        assessments = await AccountCapacityRiskService(self.session).evaluate_pool(
            owner_id=owner_id,
            platform="telegram",
            campaign_daily_limit=max(int(campaign.daily_limit_per_account), 1),
            account_ids=account_ids,
            persist_snapshots=False,
        )
        assessment_by_id = {item.account_id: item for item in assessments if item.eligible}

        accounts_result = await self.session.execute(
            select(Account).where(
                Account.owner_id == owner_id,
                Account.id.in_(assessment_by_id.keys()),
            )
        )
        accounts = list(accounts_result.scalars().all())
        reserve_percentage = min(max(float(campaign.reserve_capacity_percentage or 0.0), 0.0), 50.0)

        emergency_by_account: list[tuple[Account, int, float]] = []
        for account in accounts:
            assessment = assessment_by_id[account.id]
            warmup_limit = OrchestrationService._effective_daily_limit(account, campaign, assessment.calculated_at)
            emergency = max(min(int(assessment.suggested_daily_capacity), int(warmup_limit)), 1)
            emergency_by_account.append((account, emergency, float(assessment.health_score)))

        summary = summarize_resilience_capacities(
            [capacity for _, capacity, _ in emergency_by_account],
            reserve_percentage,
        )
        items = [
            ResilienceAccountResponse(
                account_id=account.id,
                label=account.label,
                health_score=health,
                emergency_daily_capacity=emergency,
                normal_daily_capacity=normal,
                reserved_headroom=max(emergency - normal, 0),
            )
            for (account, emergency, health), normal in zip(
                emergency_by_account,
                summary.normal_capacities,
            )
        ]

        warnings: list[str] = []
        if len(items) < 2:
            warnings.append("N-1 resilience requires at least two eligible campaign accounts.")
        if len(items) < len(account_ids):
            warnings.append("Some accounts in the original campaign pool are currently quarantined or unavailable.")
        if reserve_percentage <= 0:
            warnings.append("No explicit failover reserve is configured; normal planning may consume all safe capacity.")
        if summary.recommended_min_reserve_percentage is not None and summary.recommended_min_reserve_percentage >= 50.0 and not summary.n_minus_one_covered:
            warnings.append("The current pool is too concentrated for practical N-1 coverage under the 50% reserve ceiling.")
        if not summary.n_minus_one_covered and len(items) >= 2:
            warnings.append("Losing the highest-capacity account would reduce surviving safe capacity below current normal throughput.")

        if not items:
            status = "no_safe_capacity"
        elif summary.n_minus_one_covered:
            status = "n_minus_one_ready"
        elif len(items) < 2:
            status = "single_point_of_failure"
        else:
            status = "under_reserved"

        return CampaignResilienceResponse(
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            reserve_capacity_percentage=reserve_percentage,
            campaign_accounts=len(items),
            normal_daily_capacity=summary.normal_daily_capacity,
            emergency_daily_capacity=summary.emergency_daily_capacity,
            reserved_failover_headroom=summary.reserved_failover_headroom,
            worst_single_account_loss_capacity=summary.worst_single_account_loss_capacity,
            n_minus_one_surviving_capacity=summary.n_minus_one_surviving_capacity,
            n_minus_one_margin=summary.n_minus_one_margin,
            n_minus_one_covered=summary.n_minus_one_covered,
            resilience_ratio=summary.resilience_ratio,
            recommended_min_reserve_percentage=summary.recommended_min_reserve_percentage,
            status=status,
            warnings=warnings,
            accounts=sorted(items, key=lambda item: item.emergency_daily_capacity, reverse=True),
        )
