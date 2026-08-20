from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import ConnectorRegistry, connector_registry
from app.features.intelligence.models import AudienceMember, CommunityMembership, CommunitySnapshot
from app.features.intelligence.scoring import (
    AudienceScoreInput,
    CommunityScoreInput,
    score_audience_member,
    score_community,
)
from app.features.parser.models import ParsedChat


class IntelligenceService:
    """Build time-series community intelligence and normalized audience profiles."""

    def __init__(
        self,
        session: AsyncSession,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.session = session
        register_default_connectors()
        self.registry = registry or connector_registry

    async def enrich_community(
        self,
        *,
        owner_id: UUID,
        parsed_chat_id: UUID,
        account_id: UUID | None = None,
        member_limit: int = 2_000,
        message_limit: int = 10_000,
        lookback_days: int = 30,
        relevance_score: float | None = None,
    ) -> dict[str, Any]:
        chat = await self._get_chat(owner_id, parsed_chat_id)
        if chat is None:
            raise ValueError("Community not found")

        platform = self._resolve_platform(chat)
        connector = self.registry.get(platform)
        account = await self._get_account(owner_id, account_id)
        if account is None:
            raise ValueError(f"No active {platform} account available")

        community_ref: str | int = chat.username or chat.chat_id
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=lookback_days)

        members = await connector.get_members(
            community_ref,
            account=account,
            limit=member_limit,
        )
        messages: list[dict[str, Any]] = []
        if connector.capabilities.read_messages:
            messages = await connector.get_recent_messages(
                community_ref,
                account=account,
                since=since,
                limit=message_limit,
            )

        activity = self._aggregate_message_activity(messages, now)
        profiles = await self._upsert_members(
            owner_id=owner_id,
            platform=platform,
            members=members,
            activity=activity,
        )
        memberships = await self._upsert_memberships(
            parsed_chat_id=chat.id,
            profiles=profiles,
            activity=activity,
            relevance_score=relevance_score,
            now=now,
        )

        await self.session.flush()
        community_counts = await self._membership_counts([profile.id for profile in profiles.values()])
        for external_user_id, profile in profiles.items():
            member_activity = activity.get(external_user_id, {})
            membership = memberships.get(profile.id)
            messages_7d = int(member_activity.get("messages_7d", 0))
            messages_30d = int(member_activity.get("messages_30d", 0))

            result = score_audience_member(
                AudienceScoreInput(
                    last_activity_at=profile.last_activity_at,
                    messages_7d=messages_7d,
                    messages_30d=messages_30d,
                    communities_count=community_counts.get(profile.id, 1),
                    relevance_score=(
                        membership.relevance_score if membership is not None else relevance_score
                    ),
                    intent_score=profile.intent_score,
                    is_bot=profile.is_bot,
                    is_fake=profile.is_fake,
                    is_scam=profile.is_scam,
                    is_blacklisted=profile.is_blacklisted,
                ),
                now=now,
            )
            profile.activity_score = result.activity_score
            profile.quality_score = result.quality_score
            if relevance_score is not None:
                profile.relevance_score = max(profile.relevance_score or 0.0, relevance_score)
            profile.readiness_score = result.readiness_score

        snapshot = await self._create_snapshot(
            owner_id=owner_id,
            chat=chat,
            members=members,
            messages=messages,
            now=now,
            relevance_score=relevance_score,
        )

        chat.active_participants = snapshot.unique_authors_7d
        if chat.participants_count and snapshot.unique_authors_7d is not None:
            chat.engagement_rate = min(snapshot.unique_authors_7d / chat.participants_count, 1.0)
        chat.last_parsed_at = now

        await self.session.commit()

        return {
            "community_id": chat.id,
            "platform": platform,
            "members_sampled": len(members),
            "messages_sampled": len(messages),
            "audience_profiles": len(profiles),
            "active_1d": snapshot.active_1d or 0,
            "active_7d": snapshot.active_7d or 0,
            "messages_1d": snapshot.messages_1d or 0,
            "messages_7d": snapshot.messages_7d or 0,
            "quality_score": snapshot.quality_score or 0.0,
            "snapshot_id": snapshot.id,
            "captured_at": snapshot.captured_at,
        }

    async def list_audience(
        self,
        *,
        owner_id: UUID,
        platform: str | None = None,
        min_activity_score: float | None = None,
        min_readiness_score: float | None = None,
        include_bots: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AudienceMember], int]:
        clauses = [AudienceMember.owner_id == owner_id]
        if platform:
            clauses.append(AudienceMember.platform == platform)
        if not include_bots:
            clauses.append(AudienceMember.is_bot.is_(False))
        clauses.append(AudienceMember.is_blacklisted.is_(False))
        if min_activity_score is not None:
            clauses.append(AudienceMember.activity_score >= min_activity_score)
        if min_readiness_score is not None:
            clauses.append(AudienceMember.readiness_score >= min_readiness_score)

        count_stmt = select(func.count(AudienceMember.id)).where(*clauses)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(AudienceMember)
            .where(*clauses)
            .order_by(
                AudienceMember.readiness_score.desc().nullslast(),
                AudienceMember.activity_score.desc().nullslast(),
                AudienceMember.last_activity_at.desc().nullslast(),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def _get_chat(self, owner_id: UUID, parsed_chat_id: UUID) -> ParsedChat | None:
        result = await self.session.execute(
            select(ParsedChat).where(
                ParsedChat.id == parsed_chat_id,
                ParsedChat.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_account(self, owner_id: UUID, account_id: UUID | None) -> Account | None:
        stmt = select(Account).where(
            Account.owner_id == owner_id,
            Account.is_active.is_(True),
            Account.status == "active",
        )
        if account_id is not None:
            stmt = stmt.where(Account.id == account_id)
        stmt = stmt.order_by(Account.last_used_at.asc().nullsfirst()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _resolve_platform(chat: ParsedChat) -> str:
        metadata = chat.extra_data or {}
        explicit = metadata.get("platform")
        if explicit:
            return str(explicit).strip().lower()
        if chat.source in {
            "telegram",
            "telegram_search",
            "telegram_dialogs",
            "tgstat",
            "telemetr",
        }:
            return "telegram"
        return "telegram"

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
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
    def _aggregate_message_activity(
        cls,
        messages: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, dict[str, Any]]:
        activity: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"messages_7d": 0, "messages_30d": 0, "last_activity_at": None}
        )
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        for message in messages:
            external_user_id = message.get("external_user_id")
            created_at = cls._normalize_datetime(message.get("created_at"))
            if not external_user_id or created_at is None:
                continue
            bucket = activity[str(external_user_id)]
            if created_at >= cutoff_30d:
                bucket["messages_30d"] += 1
            if created_at >= cutoff_7d:
                bucket["messages_7d"] += 1
            if bucket["last_activity_at"] is None or created_at > bucket["last_activity_at"]:
                bucket["last_activity_at"] = created_at
        return dict(activity)

    async def _upsert_members(
        self,
        *,
        owner_id: UUID,
        platform: str,
        members: list[dict[str, Any]],
        activity: dict[str, dict[str, Any]],
    ) -> dict[str, AudienceMember]:
        external_ids = {
            str(member["external_user_id"])
            for member in members
            if member.get("external_user_id") is not None
        }
        if not external_ids:
            return {}

        existing_result = await self.session.execute(
            select(AudienceMember).where(
                AudienceMember.owner_id == owner_id,
                AudienceMember.platform == platform,
                AudienceMember.external_user_id.in_(external_ids),
            )
        )
        profiles = {item.external_user_id: item for item in existing_result.scalars().all()}

        for member_data in members:
            raw_external_id = member_data.get("external_user_id")
            if raw_external_id is None:
                continue
            external_user_id = str(raw_external_id)
            profile = profiles.get(external_user_id)
            if profile is None:
                profile = AudienceMember(
                    owner_id=owner_id,
                    platform=platform,
                    external_user_id=external_user_id,
                )
                self.session.add(profile)
                profiles[external_user_id] = profile

            profile.username = member_data.get("username") or profile.username
            profile.first_name = member_data.get("first_name") or profile.first_name
            profile.last_name = member_data.get("last_name") or profile.last_name
            profile.is_bot = bool(member_data.get("is_bot", profile.is_bot))
            profile.is_verified = bool(member_data.get("is_verified", profile.is_verified))
            profile.is_scam = bool(member_data.get("is_scam", profile.is_scam))
            profile.is_fake = bool(member_data.get("is_fake", profile.is_fake))

            candidate_times = [
                self._normalize_datetime(member_data.get("last_seen")),
                activity.get(external_user_id, {}).get("last_activity_at"),
                profile.last_activity_at,
            ]
            valid_times = [item for item in candidate_times if item is not None]
            profile.last_activity_at = max(valid_times) if valid_times else None

        await self.session.flush()
        return profiles

    async def _upsert_memberships(
        self,
        *,
        parsed_chat_id: UUID,
        profiles: dict[str, AudienceMember],
        activity: dict[str, dict[str, Any]],
        relevance_score: float | None,
        now: datetime,
    ) -> dict[UUID, CommunityMembership]:
        profile_ids = [profile.id for profile in profiles.values()]
        if not profile_ids:
            return {}

        existing_result = await self.session.execute(
            select(CommunityMembership).where(
                CommunityMembership.parsed_chat_id == parsed_chat_id,
                CommunityMembership.audience_member_id.in_(profile_ids),
            )
        )
        memberships = {
            membership.audience_member_id: membership
            for membership in existing_result.scalars().all()
        }

        for external_user_id, profile in profiles.items():
            membership = memberships.get(profile.id)
            if membership is None:
                membership = CommunityMembership(
                    audience_member_id=profile.id,
                    parsed_chat_id=parsed_chat_id,
                    first_seen_at=now,
                )
                self.session.add(membership)
                memberships[profile.id] = membership

            member_activity = activity.get(external_user_id, {})
            membership.last_seen_at = member_activity.get("last_activity_at") or profile.last_activity_at
            membership.messages_7d = int(member_activity.get("messages_7d", 0))
            membership.messages_30d = int(member_activity.get("messages_30d", 0))
            membership.relevance_score = relevance_score

        return memberships

    async def _membership_counts(self, profile_ids: list[UUID]) -> dict[UUID, int]:
        if not profile_ids:
            return {}
        result = await self.session.execute(
            select(
                CommunityMembership.audience_member_id,
                func.count(CommunityMembership.id),
            )
            .where(CommunityMembership.audience_member_id.in_(profile_ids))
            .group_by(CommunityMembership.audience_member_id)
        )
        return {member_id: int(count) for member_id, count in result.all()}

    async def _create_snapshot(
        self,
        *,
        owner_id: UUID,
        chat: ParsedChat,
        members: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        now: datetime,
        relevance_score: float | None,
    ) -> CommunitySnapshot:
        cutoff_1d = now - timedelta(days=1)
        cutoff_7d = now - timedelta(days=7)
        messages_1d = 0
        messages_7d = 0
        authors_1d: set[str] = set()
        authors_7d: set[str] = set()

        for message in messages:
            created_at = self._normalize_datetime(message.get("created_at"))
            if created_at is None:
                continue
            sender = message.get("external_user_id")
            if created_at >= cutoff_7d:
                messages_7d += 1
                if sender:
                    authors_7d.add(str(sender))
            if created_at >= cutoff_1d:
                messages_1d += 1
                if sender:
                    authors_1d.add(str(sender))

        member_ids = {
            str(member["external_user_id"])
            for member in members
            if member.get("external_user_id") is not None
        }
        bots = sum(1 for member in members if member.get("is_bot"))
        bot_ratio = bots / len(members) if members else None

        previous_result = await self.session.execute(
            select(CommunitySnapshot)
            .where(CommunitySnapshot.parsed_chat_id == chat.id)
            .order_by(CommunitySnapshot.captured_at.desc())
            .limit(1)
        )
        previous = previous_result.scalar_one_or_none()
        growth_rate_30d = None
        if (
            previous is not None
            and previous.participants_count
            and chat.participants_count is not None
            and previous.captured_at < now
        ):
            previous_time = previous.captured_at
            if previous_time.tzinfo is None:
                previous_time = previous_time.replace(tzinfo=timezone.utc)
            elapsed_days = max((now - previous_time).total_seconds() / 86400.0, 1.0)
            observed_growth = (chat.participants_count - previous.participants_count) / previous.participants_count
            growth_rate_30d = max(min(observed_growth * (30.0 / elapsed_days), 3.0), -1.0)

        community_score = score_community(
            CommunityScoreInput(
                participants_count=chat.participants_count,
                active_1d=len(authors_1d),
                active_7d=len(authors_7d),
                messages_1d=messages_1d,
                messages_7d=messages_7d,
                unique_authors_1d=len(authors_1d),
                unique_authors_7d=len(authors_7d),
                relevance_score=relevance_score,
                growth_rate_30d=growth_rate_30d,
                bot_ratio=bot_ratio,
                spam_ratio=None,
            )
        )

        snapshot = CommunitySnapshot(
            owner_id=owner_id,
            parsed_chat_id=chat.id,
            captured_at=now,
            participants_count=chat.participants_count or len(member_ids) or None,
            active_1d=len(authors_1d),
            active_7d=len(authors_7d),
            messages_1d=messages_1d,
            messages_7d=messages_7d,
            unique_authors_1d=len(authors_1d),
            unique_authors_7d=len(authors_7d),
            bot_ratio=bot_ratio,
            spam_ratio=None,
            growth_rate_30d=growth_rate_30d,
            relevance_score=relevance_score,
            quality_score=community_score.total_score,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot
