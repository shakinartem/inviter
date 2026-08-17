from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.accounts.capacity import (
    ACCOUNT_LEVEL_CODES,
    DESTINATION_LEVEL_CODES,
    HARD_COOLDOWN_CODES,
    POLICY_VERSION,
    TARGET_LEVEL_CODES,
    AccountCapacityRiskService,
)
from app.features.accounts.capacity_schemas import (
    AccountCapacityAssessmentResponse,
    AccountCapacityHistoryResponse,
    AccountCapacityPoolResponse,
    AccountCapacityRefreshRequest,
    AccountRiskPolicyResponse,
)
from app.features.accounts.models import Account


router = APIRouter(prefix="/account-capacity", tags=["account-capacity", "risk"])


@router.get("/policy", response_model=AccountRiskPolicyResponse)
async def risk_policy() -> AccountRiskPolicyResponse:
    return AccountRiskPolicyResponse(
        policy_version=POLICY_VERSION,
        account_level_codes=sorted(ACCOUNT_LEVEL_CODES),
        target_level_codes=sorted(TARGET_LEVEL_CODES),
        destination_level_codes=sorted(DESTINATION_LEVEL_CODES),
        hard_cooldown_codes=sorted(HARD_COOLDOWN_CODES),
    )


@router.post("/refresh", response_model=AccountCapacityPoolResponse)
async def refresh_capacity(
    payload: AccountCapacityRefreshRequest,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AccountCapacityPoolResponse:
    assessments = await AccountCapacityRiskService(session).evaluate_pool(
        owner_id=user.id,
        platform=payload.platform,
        campaign_daily_limit=payload.campaign_daily_limit,
        persist_snapshots=payload.persist_snapshots,
    )
    return AccountCapacityPoolResponse(
        platform=payload.platform,
        campaign_daily_limit=payload.campaign_daily_limit,
        total_accounts=len(assessments),
        eligible_accounts=sum(1 for item in assessments if item.eligible),
        quarantined_accounts=sum(1 for item in assessments if not item.eligible),
        suggested_total_daily_capacity=sum(item.suggested_daily_capacity for item in assessments if item.eligible),
        queued_jobs=sum(item.queued_jobs for item in assessments),
        average_health_score=(
            round(sum(item.health_score for item in assessments) / len(assessments), 2)
            if assessments
            else 0.0
        ),
        assessments=[AccountCapacityAssessmentResponse(**item.public_dict()) for item in assessments],
    )


@router.get("/{account_id}/history", response_model=AccountCapacityHistoryResponse)
async def capacity_history(
    account_id: UUID,
    limit: int = Query(default=50, ge=1, le=500),
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AccountCapacityHistoryResponse:
    account = (
        await session.execute(
            __import__("sqlalchemy").select(Account).where(
                Account.id == account_id,
                Account.owner_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    items = await AccountCapacityRiskService(session).history(
        owner_id=user.id,
        account_id=account_id,
        limit=limit,
    )
    return AccountCapacityHistoryResponse(
        account_id=account_id,
        items=[
            {
                "id": str(item.id),
                "health_score": item.health_score,
                "risk_score": item.risk_score,
                "capacity_multiplier": item.capacity_multiplier,
                "suggested_daily_capacity": item.suggested_daily_capacity,
                "attempts_24h": item.attempts_24h,
                "successes_24h": item.successes_24h,
                "account_errors_24h": item.account_errors_24h,
                "target_errors_24h": item.target_errors_24h,
                "floodwaits_24h": item.floodwaits_24h,
                "peer_floods_7d": item.peer_floods_7d,
                "connector_errors_24h": item.connector_errors_24h,
                "queued_jobs": item.queued_jobs,
                "eligible": item.eligible,
                "next_safe_at": item.next_safe_at.isoformat() if item.next_safe_at else None,
                "reasons": item.reasons or [],
                "calculated_at": item.calculated_at.isoformat(),
            }
            for item in items
        ],
    )
