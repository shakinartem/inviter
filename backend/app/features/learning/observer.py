from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.credentials import credential_vault
from app.features.accounts.models import Account
from app.features.connections.service import ConnectorAccountContext
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import connector_registry
from app.features.intelligence.models import AudienceMember
from app.features.learning.models import ActionFeatureSnapshot
from app.features.learning.observer_models import OutcomeObserverCursor
from app.features.learning.service import OutcomeLearningService
from app.features.orchestration.destinations import CampaignDestination
from app.features.orchestration.models import ActionJob


DEFAULT_LOOKBACK_DAYS = 30
CURSOR_OVERLAP_SECONDS = 90
RUN_STALE_MINUTES = 20
AUTOMATIC_ENGAGEMENT_CONFIDENCE = 0.8


class AutomaticOutcomeObserver:
    """Observe voluntary post-action activity without re-reading full histories.

    One connector read is performed per campaign/destination, then messages are
    matched locally to all eligible action jobs in that frozen campaign cohort.
    We intentionally label only observed activity (`messaged_destination`), not
    technical invite success and not causal conversion.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        register_default_connectors()

    async def scan_due(
        self,
        *,
        limit_campaigns: int = 50,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        message_limit: int = 5_000,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=lookback_days)
        result = await self.session.execute(
            select(
                ActionFeatureSnapshot.owner_id,
                ActionFeatureSnapshot.campaign_id,
                func.min(ActionFeatureSnapshot.first_transport_at).label("first_transport_at"),
            )
            .where(
                ActionFeatureSnapshot.first_transport_at.is_not(None),
                ActionFeatureSnapshot.first_transport_at >= cutoff,
            )
            .group_by(
                ActionFeatureSnapshot.owner_id,
                ActionFeatureSnapshot.campaign_id,
            )
            .order_by(func.min(ActionFeatureSnapshot.first_transport_at).asc())
            .limit(limit_campaigns)
        )
        campaigns = list(result.all())

        totals = {
            "campaigns_considered": len(campaigns),
            "campaigns_scanned": 0,
            "campaigns_skipped": 0,
            "campaigns_failed": 0,
            "messages_seen": 0,
            "outcomes_created": 0,
        }
        for owner_id, campaign_id, _first_transport_at in campaigns:
            try:
                scan = await self.scan_campaign(
                    owner_id=owner_id,
                    campaign_id=campaign_id,
                    lookback_days=lookback_days,
                    message_limit=message_limit,
                )
            except Exception:
                # scan_campaign persists its own diagnostic state where possible.
                totals["campaigns_failed"] += 1
                continue

            if scan.get("skipped"):
                totals["campaigns_skipped"] += 1
            else:
                totals["campaigns_scanned"] += 1
            totals["messages_seen"] += int(scan.get("messages_seen", 0))
            totals["outcomes_created"] += int(scan.get("outcomes_created", 0))
        return totals

    async def scan_campaign(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        message_limit: int = 5_000,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        destination = await self._destination(owner_id, campaign_id)
        if destination is None:
            return {"campaign_id": campaign_id, "skipped": True, "reason": "no_destination"}
        if not connector_registry.supports(destination.platform):
            return {"campaign_id": campaign_id, "skipped": True, "reason": "connector_unavailable"}

        connector = connector_registry.get(destination.platform)
        if not connector.capabilities.read_messages:
            return {"campaign_id": campaign_id, "skipped": True, "reason": "message_read_unsupported"}

        eligible = await self._eligible_actions(
            owner_id=owner_id,
            campaign_id=campaign_id,
            lookback_days=lookback_days,
            now=now,
        )
        if not eligible:
            return {"campaign_id": campaign_id, "skipped": True, "reason": "no_eligible_actions"}

        cursor = await self._cursor(owner_id, campaign_id, destination.platform)
        if self._is_recently_running(cursor, now):
            return {"campaign_id": campaign_id, "skipped": True, "reason": "observer_already_running"}

        cursor.status = "running"
        cursor.last_run_at = now
        cursor.run_count = (cursor.run_count or 0) + 1
        cursor.last_error = None
        await self.session.commit()

        since = self._scan_since(
            cursor_last_observed_at=cursor.last_observed_at,
            earliest_transport_at=min(item["first_transport_at"] for item in eligible),
            now=now,
            lookback_days=lookback_days,
        )

        account = await self._account(owner_id, destination.platform)
        if account is None:
            return await self._fail_cursor(cursor, "No active connection available for outcome observer")

        account_context: Any
        if account.platform == "telegram":
            account_context = account
        else:
            account_context = ConnectorAccountContext(
                account=account,
                credentials=credential_vault.decrypt(account.credential_payload_encrypted),
            )

        try:
            messages = await connector.get_recent_messages(
                destination.connector_ref,
                account=account_context,
                since=since,
                limit=message_limit,
            )
            outcome_count, high_water = await self._attribute_messages(
                owner_id=owner_id,
                destination=destination,
                eligible=eligible,
                messages=messages,
            )
        except Exception as exc:
            await self._fail_cursor(cursor, str(exc)[:1000])
            raise

        cursor.status = "idle"
        cursor.last_success_at = now
        cursor.last_error = None
        cursor.messages_seen = (cursor.messages_seen or 0) + len(messages)
        cursor.outcomes_created = (cursor.outcomes_created or 0) + outcome_count
        if high_water is not None:
            current = self._aware(cursor.last_observed_at) if cursor.last_observed_at else None
            cursor.last_observed_at = max(current, high_water) if current else high_water
        await self.session.commit()

        return {
            "campaign_id": campaign_id,
            "platform": destination.platform,
            "since": since,
            "messages_seen": len(messages),
            "outcomes_created": outcome_count,
            "last_observed_at": cursor.last_observed_at,
            "skipped": False,
        }

    async def status(self, *, owner_id: UUID, limit: int = 100) -> list[OutcomeObserverCursor]:
        result = await self.session.execute(
            select(OutcomeObserverCursor)
            .where(OutcomeObserverCursor.owner_id == owner_id)
            .order_by(OutcomeObserverCursor.last_run_at.desc().nullslast())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _eligible_actions(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID,
        lookback_days: int,
        now: datetime,
    ) -> list[dict[str, Any]]:
        cutoff = now - timedelta(days=lookback_days)
        result = await self.session.execute(
            select(ActionFeatureSnapshot, ActionJob, AudienceMember)
            .join(ActionJob, ActionJob.id == ActionFeatureSnapshot.action_job_id)
            .join(AudienceMember, AudienceMember.id == ActionFeatureSnapshot.audience_member_id)
            .where(
                ActionFeatureSnapshot.owner_id == owner_id,
                ActionFeatureSnapshot.campaign_id == campaign_id,
                ActionFeatureSnapshot.first_transport_at.is_not(None),
                ActionFeatureSnapshot.first_transport_at >= cutoff,
                ActionJob.attempts > 0,
                AudienceMember.is_bot.is_(False),
            )
        )
        items: list[dict[str, Any]] = []
        for snapshot, job, member in result.all():
            items.append(
                {
                    "job_id": job.id,
                    "audience_member_id": member.id,
                    "external_user_id": member.external_user_id,
                    "first_transport_at": self._aware(snapshot.first_transport_at),
                }
            )
        return items

    async def _attribute_messages(
        self,
        *,
        owner_id: UUID,
        destination: CampaignDestination,
        eligible: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> tuple[int, datetime | None]:
        by_external_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in eligible:
            by_external_user[str(item["external_user_id"])].append(item)

        learning = OutcomeLearningService(self.session)
        outcomes_created = 0
        high_water: datetime | None = None

        # Oldest first makes attribution deterministic when several messages are
        # returned in reverse chronological order by a connector.
        normalized_messages: list[tuple[datetime, dict[str, Any]]] = []
        for message in messages:
            observed_at = self._normalize_datetime(message.get("created_at"))
            if observed_at is None:
                continue
            normalized_messages.append((observed_at, message))
        normalized_messages.sort(key=lambda pair: pair[0])

        seen_jobs: set[UUID] = set()
        for observed_at, message in normalized_messages:
            high_water = observed_at if high_water is None or observed_at > high_water else high_water
            external_user_id = message.get("external_user_id")
            external_message_id = message.get("external_message_id")
            if not external_user_id or not external_message_id:
                continue

            for action in by_external_user.get(str(external_user_id), []):
                if action["job_id"] in seen_jobs:
                    continue
                first_transport_at = action["first_transport_at"]
                if observed_at < first_transport_at:
                    continue

                latency_seconds = max((observed_at - first_transport_at).total_seconds(), 0.0)
                event = await learning.record_observed_outcome(
                    owner_id=owner_id,
                    action_job_id=action["job_id"],
                    stage="engagement",
                    event_type="messaged_destination",
                    success=True,
                    source=f"{destination.platform}_observer",
                    confidence=AUTOMATIC_ENGAGEMENT_CONFIDENCE,
                    observed_at=observed_at,
                    external_event_id=(
                        f"{destination.external_id}:{external_message_id}"
                    ),
                    properties={
                        "destination_external_id": destination.external_id,
                        "external_message_id": str(external_message_id),
                        "is_reply": bool(message.get("is_reply")),
                        "latency_seconds": round(latency_seconds, 3),
                        "attribution": "post_action_destination_activity",
                    },
                )
                if event is not None:
                    outcomes_created += 1
                seen_jobs.add(action["job_id"])
                # One engagement label per job is enough for this event type. The
                # raw messages remain in the source platform, not our database.
                break

        return outcomes_created, high_water

    async def _destination(
        self,
        owner_id: UUID,
        campaign_id: UUID,
    ) -> CampaignDestination | None:
        result = await self.session.execute(
            select(CampaignDestination).where(
                CampaignDestination.owner_id == owner_id,
                CampaignDestination.campaign_id == campaign_id,
            )
        )
        return result.scalar_one_or_none()

    async def _account(self, owner_id: UUID, platform: str) -> Account | None:
        result = await self.session.execute(
            select(Account)
            .where(
                Account.owner_id == owner_id,
                Account.platform == platform,
                Account.is_active.is_(True),
                Account.status == "active",
            )
            .order_by(
                Account.health_score.desc(),
                Account.last_used_at.asc().nullsfirst(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _cursor(
        self,
        owner_id: UUID,
        campaign_id: UUID,
        platform: str,
    ) -> OutcomeObserverCursor:
        result = await self.session.execute(
            select(OutcomeObserverCursor).where(
                OutcomeObserverCursor.owner_id == owner_id,
                OutcomeObserverCursor.campaign_id == campaign_id,
            )
        )
        cursor = result.scalar_one_or_none()
        if cursor is not None:
            return cursor
        cursor = OutcomeObserverCursor(
            owner_id=owner_id,
            campaign_id=campaign_id,
            platform=platform,
            status="idle",
            messages_seen=0,
            outcomes_created=0,
            run_count=0,
        )
        self.session.add(cursor)
        await self.session.commit()
        await self.session.refresh(cursor)
        return cursor

    async def _fail_cursor(
        self,
        cursor: OutcomeObserverCursor,
        error: str,
    ) -> dict[str, Any]:
        cursor.status = "error"
        cursor.last_error = error[:1000]
        await self.session.commit()
        return {
            "campaign_id": cursor.campaign_id,
            "platform": cursor.platform,
            "messages_seen": 0,
            "outcomes_created": 0,
            "skipped": True,
            "reason": "observer_error",
            "error": cursor.last_error,
        }

    @staticmethod
    def _is_recently_running(cursor: OutcomeObserverCursor, now: datetime) -> bool:
        if cursor.status != "running" or cursor.last_run_at is None:
            return False
        return AutomaticOutcomeObserver._aware(cursor.last_run_at) >= now - timedelta(minutes=RUN_STALE_MINUTES)

    @staticmethod
    def _scan_since(
        *,
        cursor_last_observed_at: datetime | None,
        earliest_transport_at: datetime,
        now: datetime,
        lookback_days: int,
    ) -> datetime:
        lower_bound = now - timedelta(days=lookback_days)
        earliest = max(AutomaticOutcomeObserver._aware(earliest_transport_at), lower_bound)
        if cursor_last_observed_at is None:
            return earliest
        overlapped = AutomaticOutcomeObserver._aware(cursor_last_observed_at) - timedelta(
            seconds=CURSOR_OVERLAP_SECONDS
        )
        return max(overlapped, earliest)

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return AutomaticOutcomeObserver._aware(value)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return AutomaticOutcomeObserver._aware(parsed)
        return None

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
