from __future__ import annotations

import hashlib
import math
import secrets
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.models import CampaignExperiment, ExperimentAssignment


class CampaignExperimentService:
    """Configure and freeze deterministic treatment/holdout assignments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_configuration(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        holdout_percentage: float,
        commit: bool = False,
    ) -> CampaignExperiment | None:
        pct = float(holdout_percentage)
        if pct <= 0:
            return None
        if pct > 50:
            raise ValueError("holdout_percentage cannot exceed 50")

        existing = await self.get_for_campaign(owner_id=owner_id, campaign_id=campaign_id)
        if existing is not None:
            raise ValueError("Campaign already has an experiment configuration")

        experiment = CampaignExperiment(
            owner_id=owner_id,
            campaign_id=campaign_id,
            holdout_percentage=pct,
            assignment_salt=secrets.token_hex(32),
            status="configured",
            action_budget=None,
            candidate_pool_size=0,
            treatment_count=0,
            holdout_count=0,
            assigned_at=None,
        )
        self.session.add(experiment)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(experiment)
        return experiment

    async def get_for_campaign(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
    ) -> CampaignExperiment | None:
        result = await self.session.execute(
            select(CampaignExperiment).where(
                CampaignExperiment.owner_id == owner_id,
                CampaignExperiment.campaign_id == campaign_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: UUID) -> list[CampaignExperiment]:
        result = await self.session.execute(
            select(CampaignExperiment)
            .where(CampaignExperiment.owner_id == owner_id)
            .order_by(CampaignExperiment.created_at.desc())
        )
        return list(result.scalars().all())

    async def assignments(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        variant: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ExperimentAssignment], int]:
        experiment = await self.get_for_campaign(owner_id=owner_id, campaign_id=campaign_id)
        if experiment is None:
            raise ValueError("Campaign experiment not found")
        clauses = [ExperimentAssignment.experiment_id == experiment.id]
        if variant:
            normalized = variant.strip().lower()
            if normalized not in {"treatment", "holdout"}:
                raise ValueError("variant must be treatment or holdout")
            clauses.append(ExperimentAssignment.variant == normalized)
        total = int(
            (
                await self.session.execute(
                    select(func.count(ExperimentAssignment.id)).where(*clauses)
                )
            ).scalar()
            or 0
        )
        result = await self.session.execute(
            select(ExperimentAssignment)
            .where(*clauses)
            .order_by(ExperimentAssignment.rank.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def assign_ranked_pool(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        ranked_member_ids: list[UUID],
        action_budget: int,
    ) -> tuple[CampaignExperiment | None, set[UUID] | None]:
        experiment = await self.get_for_campaign(owner_id=owner_id, campaign_id=campaign_id)
        if experiment is None:
            return None, None
        if action_budget < 1:
            raise ValueError("action budget must be positive")

        if experiment.status == "assigned":
            if experiment.action_budget != action_budget:
                raise ValueError(
                    f"Experiment action budget is frozen at {experiment.action_budget}; recreate the campaign to use a different budget"
                )
            result = await self.session.execute(
                select(ExperimentAssignment.audience_member_id).where(
                    ExperimentAssignment.experiment_id == experiment.id,
                    ExperimentAssignment.variant == "treatment",
                )
            )
            return experiment, set(result.scalars().all())

        if experiment.status != "configured":
            raise ValueError(f"Campaign experiment cannot be assigned from status: {experiment.status}")

        # Keep the ranked universe fixed. When enough candidates exist, reserve
        # just enough holdout units so the remainder is exactly action_budget.
        desired_pool_size = self.required_pool_size(
            action_budget=action_budget,
            holdout_percentage=experiment.holdout_percentage,
        )
        pool = list(dict.fromkeys(ranked_member_ids))[:desired_pool_size]
        if not pool:
            raise ValueError("Experiment candidate pool is empty")

        holdout_count = self.holdout_count_for_pool(
            pool_size=len(pool),
            action_budget=action_budget,
            holdout_percentage=experiment.holdout_percentage,
            full_pool_available=len(pool) >= desired_pool_size,
        )
        holdout_ids = self.select_holdout_ids(
            member_ids=pool,
            holdout_count=holdout_count,
            assignment_salt=experiment.assignment_salt,
        )
        now = datetime.now(timezone.utc)
        treatment_ids: set[UUID] = set()
        for rank, member_id in enumerate(pool, start=1):
            variant = "holdout" if member_id in holdout_ids else "treatment"
            if variant == "treatment":
                treatment_ids.add(member_id)
            self.session.add(
                ExperimentAssignment(
                    owner_id=owner_id,
                    experiment_id=experiment.id,
                    campaign_id=campaign_id,
                    audience_member_id=member_id,
                    variant=variant,
                    rank=rank,
                    assigned_at=now,
                )
            )

        experiment.action_budget = action_budget
        experiment.candidate_pool_size = len(pool)
        experiment.treatment_count = len(treatment_ids)
        experiment.holdout_count = len(holdout_ids)
        experiment.status = "assigned"
        experiment.assigned_at = now
        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment, treatment_ids

    @staticmethod
    def required_pool_size(*, action_budget: int, holdout_percentage: float) -> int:
        pct = max(0.0, min(float(holdout_percentage), 50.0)) / 100.0
        if pct <= 0:
            return action_budget
        return max(action_budget + 1, math.ceil(action_budget / (1.0 - pct)))

    @staticmethod
    def holdout_count_for_pool(
        *,
        pool_size: int,
        action_budget: int,
        holdout_percentage: float,
        full_pool_available: bool,
    ) -> int:
        if pool_size <= 1:
            return 0
        if full_pool_available and pool_size > action_budget:
            return pool_size - action_budget
        requested = int(round(pool_size * float(holdout_percentage) / 100.0))
        return min(max(requested, 1), pool_size - 1)

    @staticmethod
    def select_holdout_ids(
        *,
        member_ids: Iterable[UUID],
        holdout_count: int,
        assignment_salt: str,
    ) -> set[UUID]:
        unique = list(dict.fromkeys(member_ids))
        if holdout_count <= 0:
            return set()
        holdout_count = min(holdout_count, max(len(unique) - 1, 0))
        ranked = sorted(
            unique,
            key=lambda member_id: hashlib.sha256(
                f"{assignment_salt}:{member_id}".encode("utf-8")
            ).digest(),
        )
        return set(ranked[:holdout_count])
