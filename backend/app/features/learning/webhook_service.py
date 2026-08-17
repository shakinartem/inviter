from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.credentials import credential_vault
from app.features.learning.models import ActionFeatureSnapshot, OutcomeEvent
from app.features.learning.service import OutcomeLearningService
from app.features.learning.webhook_models import OutcomeWebhookSource
from app.features.learning.webhook_schemas import (
    WebhookOutcomePayload,
    WebhookSourceCreate,
    WebhookSourceUpdate,
)
from app.features.orchestration.models import ActionJob


MAX_BODY_BYTES = 64 * 1024
REPLAY_WINDOW_SECONDS = 300
FUTURE_EVENT_TOLERANCE = timedelta(minutes=5)


class WebhookSourceNotFound(ValueError):
    pass


class WebhookAuthenticationError(ValueError):
    pass


class WebhookPayloadError(ValueError):
    pass


class WebhookPolicyError(ValueError):
    pass


class OutcomeWebhookService:
    """Manage encrypted signing sources and ingest verified downstream outcomes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_source(
        self,
        owner_id: UUID,
        payload: WebhookSourceCreate,
    ) -> tuple[OutcomeWebhookSource, str]:
        credential_vault.require_secure_configuration()
        name = payload.name.strip()
        slug = self._normalize_slug(payload.slug or name)
        existing = await self.session.execute(
            select(OutcomeWebhookSource.id).where(
                OutcomeWebhookSource.owner_id == owner_id,
                OutcomeWebhookSource.slug == slug,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("A webhook source with this slug already exists")

        signing_secret = secrets.token_urlsafe(32)
        encrypted = credential_vault.encrypt({"signing_secret": signing_secret})
        if encrypted is None:
            raise ValueError("Could not encrypt webhook signing secret")

        source = OutcomeWebhookSource(
            owner_id=owner_id,
            name=name,
            slug=slug,
            signing_secret_encrypted=encrypted,
            allowed_stages=list(dict.fromkeys(payload.allowed_stages)),
            allowed_event_types=payload.allowed_event_types,
            is_active=True,
            delivery_count=0,
            accepted_count=0,
            rejected_count=0,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source, signing_secret

    async def list_sources(self, owner_id: UUID) -> list[OutcomeWebhookSource]:
        result = await self.session.execute(
            select(OutcomeWebhookSource)
            .where(OutcomeWebhookSource.owner_id == owner_id)
            .order_by(OutcomeWebhookSource.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_source(self, owner_id: UUID, source_id: UUID) -> OutcomeWebhookSource | None:
        result = await self.session.execute(
            select(OutcomeWebhookSource).where(
                OutcomeWebhookSource.id == source_id,
                OutcomeWebhookSource.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_source(
        self,
        owner_id: UUID,
        source_id: UUID,
        payload: WebhookSourceUpdate,
    ) -> OutcomeWebhookSource:
        source = await self.get_source(owner_id, source_id)
        if source is None:
            raise WebhookSourceNotFound("Webhook source not found")
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            source.name = str(updates["name"]).strip()
        if "is_active" in updates:
            source.is_active = bool(updates["is_active"])
        if "allowed_stages" in updates and updates["allowed_stages"] is not None:
            source.allowed_stages = list(dict.fromkeys(updates["allowed_stages"]))
        if "allowed_event_types" in updates and updates["allowed_event_types"] is not None:
            source.allowed_event_types = updates["allowed_event_types"]
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def rotate_secret(self, owner_id: UUID, source_id: UUID) -> tuple[OutcomeWebhookSource, str]:
        source = await self.get_source(owner_id, source_id)
        if source is None:
            raise WebhookSourceNotFound("Webhook source not found")
        credential_vault.require_secure_configuration()
        signing_secret = secrets.token_urlsafe(32)
        encrypted = credential_vault.encrypt({"signing_secret": signing_secret})
        if encrypted is None:
            raise ValueError("Could not encrypt webhook signing secret")
        source.signing_secret_encrypted = encrypted
        source.secret_rotated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(source)
        return source, signing_secret

    async def ingest(
        self,
        *,
        source_id: UUID,
        timestamp_header: str,
        signature_header: str,
        raw_body: bytes,
    ) -> tuple[OutcomeEvent, bool]:
        source = await self._public_source(source_id)
        if source is None:
            raise WebhookSourceNotFound("Webhook source not found")
        now = datetime.now(timezone.utc)

        try:
            if not source.is_active:
                raise WebhookPolicyError("Webhook source is inactive")
            if len(raw_body) > MAX_BODY_BYTES:
                raise WebhookPayloadError("Webhook body exceeds 64 KiB")

            timestamp = self._parse_and_validate_timestamp(timestamp_header)
            signing_secret = self._signing_secret(source)
            if not self.verify_signature(
                signing_secret=signing_secret,
                timestamp=str(timestamp),
                raw_body=raw_body,
                signature_header=signature_header,
            ):
                raise WebhookAuthenticationError("Invalid webhook signature")

            try:
                payload = WebhookOutcomePayload.model_validate_json(raw_body)
            except ValidationError as exc:
                raise WebhookPayloadError("Invalid webhook outcome payload") from exc

            if payload.stage not in (source.allowed_stages or []):
                raise WebhookPolicyError(f"Stage is not allowed for this source: {payload.stage}")
            allowed_types = source.allowed_event_types or []
            if allowed_types and payload.event_type not in allowed_types:
                raise WebhookPolicyError(f"Event type is not allowed for this source: {payload.event_type}")

            observed_at = self._aware(payload.observed_at)
            if observed_at > now + FUTURE_EVENT_TOLERANCE:
                raise WebhookPayloadError("observed_at is too far in the future")

            idempotency_key = f"{source.id}:{payload.event_id}"
            dedupe_key = f"idempotency:webhook:{idempotency_key}"[:255]
            existing_result = await self.session.execute(
                select(OutcomeEvent).where(
                    OutcomeEvent.owner_id == source.owner_id,
                    OutcomeEvent.dedupe_key == dedupe_key,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                await self._mark_accepted(source.id, now)
                return existing, True

            # A downstream label may only be attached to an action that actually
            # reached transport. This prevents a CRM event from manufacturing a
            # conversion label for a merely planned/unexecuted job and preserves
            # the decision-time feature vector instead of creating one after the fact.
            attribution_result = await self.session.execute(
                select(ActionFeatureSnapshot, ActionJob)
                .join(ActionJob, ActionJob.id == ActionFeatureSnapshot.action_job_id)
                .where(
                    ActionFeatureSnapshot.owner_id == source.owner_id,
                    ActionFeatureSnapshot.action_job_id == payload.action_job_id,
                )
            )
            attribution = attribution_result.one_or_none()
            if attribution is None:
                raise WebhookPayloadError("Action has no decision-time snapshot")
            snapshot, job = attribution
            if job.attempts <= 0 or snapshot.first_transport_at is None:
                raise WebhookPayloadError("Action has not reached transport")
            first_transport_at = self._aware(snapshot.first_transport_at)
            if observed_at < first_transport_at:
                raise WebhookPayloadError("observed_at predates the attributed action")

            body_sha256 = hashlib.sha256(raw_body).hexdigest()
            properties = dict(payload.properties or {})
            properties.update(
                {
                    "webhook_source_id": str(source.id),
                    "webhook_source_slug": source.slug,
                    "payload_sha256": body_sha256,
                }
            )
            event = await OutcomeLearningService(self.session).record_observed_outcome(
                owner_id=source.owner_id,
                action_job_id=payload.action_job_id,
                stage=payload.stage,
                event_type=payload.event_type,
                success=payload.success,
                source="webhook",
                confidence=payload.confidence,
                value=payload.value,
                observed_at=observed_at,
                external_event_id=payload.event_id,
                idempotency_key=idempotency_key,
                properties=properties,
            )
            await self._mark_accepted(source.id, now)
            return event, False
        except Exception as exc:
            await self._mark_rejected(source.id, now, str(exc)[:1000])
            raise

    async def _public_source(self, source_id: UUID) -> OutcomeWebhookSource | None:
        result = await self.session.execute(select(OutcomeWebhookSource).where(OutcomeWebhookSource.id == source_id))
        return result.scalar_one_or_none()

    @staticmethod
    def signing_payload(timestamp: str, raw_body: bytes) -> bytes:
        return timestamp.encode("ascii") + b"." + raw_body

    @classmethod
    def signature_for(cls, signing_secret: str, timestamp: str, raw_body: bytes) -> str:
        digest = hmac.new(
            signing_secret.encode("utf-8"),
            cls.signing_payload(timestamp, raw_body),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    @classmethod
    def verify_signature(
        cls,
        *,
        signing_secret: str,
        timestamp: str,
        raw_body: bytes,
        signature_header: str,
    ) -> bool:
        expected = cls.signature_for(signing_secret, timestamp, raw_body)
        return hmac.compare_digest(expected, signature_header.strip().lower())

    @staticmethod
    def _parse_and_validate_timestamp(value: str) -> int:
        try:
            timestamp = int(value)
        except (TypeError, ValueError) as exc:
            raise WebhookAuthenticationError("Invalid webhook timestamp") from exc
        if abs(int(time.time()) - timestamp) > REPLAY_WINDOW_SECONDS:
            raise WebhookAuthenticationError("Webhook timestamp is outside the replay window")
        return timestamp

    @staticmethod
    def _signing_secret(source: OutcomeWebhookSource) -> str:
        credentials = credential_vault.decrypt(source.signing_secret_encrypted)
        secret = credentials.get("signing_secret")
        if not isinstance(secret, str) or not secret:
            raise WebhookAuthenticationError("Webhook source credential is unavailable")
        return secret

    async def _mark_accepted(self, source_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(OutcomeWebhookSource)
            .where(OutcomeWebhookSource.id == source_id)
            .values(
                delivery_count=OutcomeWebhookSource.delivery_count + 1,
                accepted_count=OutcomeWebhookSource.accepted_count + 1,
                last_received_at=now,
                last_accepted_at=now,
                last_error=None,
            )
        )
        await self.session.commit()

    async def _mark_rejected(self, source_id: UUID, now: datetime, error: str) -> None:
        await self.session.rollback()
        await self.session.execute(
            update(OutcomeWebhookSource)
            .where(OutcomeWebhookSource.id == source_id)
            .values(
                delivery_count=OutcomeWebhookSource.delivery_count + 1,
                rejected_count=OutcomeWebhookSource.rejected_count + 1,
                last_received_at=now,
                last_failure_at=now,
                last_error=error,
            )
        )
        await self.session.commit()

    @staticmethod
    def _normalize_slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return (slug or f"source-{secrets.token_hex(4)}")[:64]

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
