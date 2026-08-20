from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.credentials import credential_vault
from app.features.accounts.models import Account
from app.features.connections.service import ConnectorAccountContext
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import connector_registry
from app.features.intelligence.intent import MODEL_VERSION, aggregate_intent, score_message
from app.features.intelligence.models import AudienceMember, IntentSignal
from app.features.parser.models import ParsedChat


class IntentSignalService:
    """Extract, persist and aggregate explainable future-action signals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        register_default_connectors()

    async def scan_community(
        self,
        *,
        owner_id: UUID,
        parsed_chat_id: UUID,
        account_id: UUID | None = None,
        lookback_days: int = 30,
        message_limit: int = 10_000,
        minimum_score: float = 12.0,
    ) -> dict[str, Any]:
        chat = await self._chat(owner_id, parsed_chat_id)
        if chat is None:
            raise ValueError("Community not found")

        platform = self._platform(chat)
        connector = connector_registry.get(platform)
        if not connector.capabilities.read_messages:
            raise ValueError(f"{platform} connection cannot read messages for intent scoring")

        account = await self._account(owner_id, platform, account_id)
        if account is None:
            raise ValueError(f"No active {platform} connection is available")
        connector_account: Account | ConnectorAccountContext
        if platform == "telegram":
            connector_account = account
        else:
            connector_account = ConnectorAccountContext(
                account=account,
                credentials=credential_vault.decrypt(account.credential_payload_encrypted),
            )

        now = datetime.now(timezone.utc)
        since = now - timedelta(days=lookback_days)
        community_ref: str | int = chat.username or chat.chat_id
        messages = await connector.get_recent_messages(
            community_ref,
            account=connector_account,
            since=since,
            limit=message_limit,
        )

        sender_ids = {
            str(message["external_user_id"])
            for message in messages
            if message.get("external_user_id") is not None
        }
        if not sender_ids:
            return self._empty_result(chat, platform, len(messages))

        profile_result = await self.session.execute(
            select(AudienceMember).where(
                AudienceMember.owner_id == owner_id,
                AudienceMember.platform == platform,
                AudienceMember.external_user_id.in_(sender_ids),
            )
        )
        profiles = {
            member.external_user_id: member for member in profile_result.scalars().all()
        }
        if not profiles:
            return self._empty_result(chat, platform, len(messages))

        topic = chat.niche or chat.category or chat.title
        candidates: list[tuple[dict[str, Any], AudienceMember, Any, str]] = []
        fingerprints: set[str] = set()
        for message in messages:
            sender_id = message.get("external_user_id")
            text = str(message.get("text") or "").strip()
            if sender_id is None or not text:
                continue
            profile = profiles.get(str(sender_id))
            if profile is None or profile.is_bot or profile.is_blacklisted:
                continue

            evidence = score_message(text, topic=topic, minimum_score=minimum_score)
            if evidence is None:
                continue
            fingerprint = self._fingerprint(platform, chat.id, message)
            fingerprints.add(fingerprint)
            candidates.append((message, profile, evidence, fingerprint))

        if not candidates:
            await self._refresh_member_intent(owner_id, list(profiles.values()), now)
            await self.session.commit()
            return self._empty_result(chat, platform, len(messages))

        existing_result = await self.session.execute(
            select(IntentSignal.message_fingerprint).where(
                IntentSignal.owner_id == owner_id,
                IntentSignal.platform == platform,
                IntentSignal.message_fingerprint.in_(fingerprints),
                IntentSignal.model_version == MODEL_VERSION,
            )
        )
        existing = set(existing_result.scalars().all())

        created = 0
        affected: dict[UUID, AudienceMember] = {}
        strongest = 0.0
        signal_types: dict[str, int] = defaultdict(int)
        for message, profile, evidence, fingerprint in candidates:
            if fingerprint in existing:
                affected[profile.id] = profile
                continue
            observed_at = self._datetime(message.get("created_at")) or now
            signal = IntentSignal(
                owner_id=owner_id,
                audience_member_id=profile.id,
                parsed_chat_id=chat.id,
                platform=platform,
                external_message_id=(
                    str(message["external_message_id"])
                    if message.get("external_message_id") is not None
                    else None
                ),
                message_fingerprint=fingerprint,
                observed_at=observed_at,
                signal_type=evidence.signal_type,
                topic=topic,
                score=evidence.score,
                confidence=evidence.confidence,
                model_version=evidence.model_version,
                features=evidence.features,
            )
            self.session.add(signal)
            existing.add(fingerprint)
            affected[profile.id] = profile
            created += 1
            strongest = max(strongest, evidence.score)
            signal_types[evidence.signal_type] += 1

        await self.session.flush()
        await self._refresh_member_intent(owner_id, list(affected.values()), now)
        await self.session.commit()

        intent_scores = [profile.intent_score or 0.0 for profile in affected.values()]
        return {
            "community_id": chat.id,
            "platform": platform,
            "messages_scanned": len(messages),
            "candidate_signals": len(candidates),
            "signals_created": created,
            "members_scored": len(affected),
            "strongest_signal": round(strongest, 2),
            "average_member_intent": (
                round(sum(intent_scores) / len(intent_scores), 2) if intent_scores else 0.0
            ),
            "signal_types": dict(sorted(signal_types.items())),
            "model_version": MODEL_VERSION,
            "scanned_at": now,
        }

    async def list_signals(
        self,
        *,
        owner_id: UUID,
        audience_member_id: UUID | None = None,
        parsed_chat_id: UUID | None = None,
        min_score: float | None = None,
        limit: int = 100,
    ) -> list[IntentSignal]:
        stmt = select(IntentSignal).where(IntentSignal.owner_id == owner_id)
        if audience_member_id is not None:
            stmt = stmt.where(IntentSignal.audience_member_id == audience_member_id)
        if parsed_chat_id is not None:
            stmt = stmt.where(IntentSignal.parsed_chat_id == parsed_chat_id)
        if min_score is not None:
            stmt = stmt.where(IntentSignal.score >= min_score)
        result = await self.session.execute(
            stmt.order_by(
                IntentSignal.observed_at.desc(),
                IntentSignal.score.desc(),
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def _refresh_member_intent(
        self,
        owner_id: UUID,
        members: list[AudienceMember],
        now: datetime,
    ) -> None:
        if not members:
            return
        member_ids = [member.id for member in members]
        since = now - timedelta(days=90)
        result = await self.session.execute(
            select(IntentSignal).where(
                IntentSignal.owner_id == owner_id,
                IntentSignal.audience_member_id.in_(member_ids),
                IntentSignal.observed_at >= since,
            )
        )
        by_member: dict[UUID, list[IntentSignal]] = defaultdict(list)
        for signal in result.scalars().all():
            by_member[signal.audience_member_id].append(signal)

        for member in members:
            signals = by_member.get(member.id, [])
            aggregate = aggregate_intent(
                (
                    (signal.score, signal.confidence, signal.observed_at, signal.signal_type)
                    for signal in signals
                ),
                now=now,
            )
            member.intent_score = aggregate.score
            member.readiness_score = self._readiness(
                activity=member.activity_score,
                relevance=member.relevance_score,
                quality=member.quality_score,
                intent=member.intent_score,
                blocked=member.is_bot or member.is_blacklisted,
            )

    async def _chat(self, owner_id: UUID, parsed_chat_id: UUID) -> ParsedChat | None:
        result = await self.session.execute(
            select(ParsedChat).where(
                ParsedChat.id == parsed_chat_id,
                ParsedChat.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def _account(
        self,
        owner_id: UUID,
        platform: str,
        account_id: UUID | None,
    ) -> Account | None:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.platform == platform,
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_id is not None:
            stmt = stmt.where(Account.id == account_id)
        result = await self.session.execute(
            stmt.order_by(
                Account.health_score.desc(),
                Account.last_used_at.asc().nullsfirst(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _platform(chat: ParsedChat) -> str:
        metadata = chat.extra_data or {}
        return str(metadata.get("platform") or "telegram").strip().lower()

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @classmethod
    def _fingerprint(
        cls,
        platform: str,
        parsed_chat_id: UUID,
        message: dict[str, Any],
    ) -> str:
        message_id = message.get("external_message_id")
        if message_id is not None:
            material = f"{platform}|{parsed_chat_id}|id:{message_id}"
        else:
            observed = cls._datetime(message.get("created_at"))
            material = "|".join(
                [
                    platform,
                    str(parsed_chat_id),
                    str(message.get("external_user_id") or ""),
                    observed.isoformat() if observed else "",
                    str(message.get("text") or "").casefold().strip(),
                ]
            )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _readiness(
        *,
        activity: float | None,
        relevance: float | None,
        quality: float | None,
        intent: float | None,
        blocked: bool,
    ) -> float:
        if blocked:
            return 0.0
        value = (
            max(min(activity or 0.0, 100.0), 0.0) * 0.45
            + max(min(relevance or 0.0, 100.0), 0.0) * 0.20
            + max(min(quality or 0.0, 100.0), 0.0) * 0.15
            + max(min(intent or 0.0, 100.0), 0.0) * 0.20
        )
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _empty_result(chat: ParsedChat, platform: str, messages_scanned: int) -> dict[str, Any]:
        return {
            "community_id": chat.id,
            "platform": platform,
            "messages_scanned": messages_scanned,
            "candidate_signals": 0,
            "signals_created": 0,
            "members_scored": 0,
            "strongest_signal": 0.0,
            "average_member_intent": 0.0,
            "signal_types": {},
            "model_version": MODEL_VERSION,
            "scanned_at": datetime.now(timezone.utc),
        }
