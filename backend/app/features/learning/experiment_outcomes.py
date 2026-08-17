from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.experiments.models import ExperimentAssignment
from app.features.intelligence.models import AudienceMember
from app.features.learning.models import OutcomeEvent


class ExperimentOutcomeService:
    """Append engagement/business labels to a randomized unit without an ActionJob."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_assignment_outcome(
        self,
        *,
        owner_id: UUID,
        experiment_assignment_id: UUID,
        stage: str,
        event_type: str,
        success: bool | None = True,
        source: str = "webhook",
        confidence: float = 1.0,
        value: float | None = None,
        observed_at: datetime | None = None,
        external_event_id: str | None = None,
        idempotency_key: str | None = None,
        properties: dict | None = None,
    ) -> OutcomeEvent:
        result = await self.session.execute(
            select(ExperimentAssignment, AudienceMember)
            .join(AudienceMember, AudienceMember.id == ExperimentAssignment.audience_member_id)
            .where(
                ExperimentAssignment.id == experiment_assignment_id,
                ExperimentAssignment.owner_id == owner_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise ValueError("Experiment assignment not found")
        assignment, member = row

        normalized_stage = stage.strip().lower()
        normalized_type = event_type.strip().lower().replace(" ", "_")
        normalized_source = source.strip().lower().replace(" ", "_")
        if normalized_stage not in {"engagement", "business"}:
            raise ValueError("Experiment outcomes must be engagement or business stage")
        if not normalized_type:
            raise ValueError("event_type is required")

        observed = self._aware(observed_at or datetime.now(timezone.utc))
        assigned_at = self._aware(assignment.assigned_at)
        if observed < assigned_at:
            raise ValueError("observed_at predates randomized assignment")

        dedupe_key = self._dedupe_key(
            assignment_id=assignment.id,
            stage=normalized_stage,
            event_type=normalized_type,
            source=normalized_source,
            observed_at=observed,
            external_event_id=external_event_id,
            idempotency_key=idempotency_key,
        )
        existing_result = await self.session.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.owner_id == owner_id,
                OutcomeEvent.dedupe_key == dedupe_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        event = OutcomeEvent(
            owner_id=owner_id,
            action_job_id=None,
            experiment_assignment_id=assignment.id,
            campaign_id=assignment.campaign_id,
            audience_member_id=assignment.audience_member_id,
            platform=member.platform,
            stage=normalized_stage,
            event_type=normalized_type,
            success=success,
            source=normalized_source,
            confidence=max(0.0, min(float(confidence), 1.0)),
            value=value,
            observed_at=observed,
            external_event_id=external_event_id,
            dedupe_key=dedupe_key,
            properties=properties,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    @staticmethod
    def _dedupe_key(
        *,
        assignment_id: UUID,
        stage: str,
        event_type: str,
        source: str,
        observed_at: datetime,
        external_event_id: str | None,
        idempotency_key: str | None,
    ) -> str:
        if idempotency_key:
            return f"idempotency:{source}:{idempotency_key}"[:255]
        if external_event_id:
            return f"external:{source}:{external_event_id}"[:255]
        raw = f"{assignment_id}|{stage}|{event_type}|{source}|{observed_at.isoformat()}"
        return f"derived:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
