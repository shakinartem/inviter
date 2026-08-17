from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.features.inviter.models import InviteCampaign
from app.features.parser.models import ParsedChat


class CampaignDestination(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical community destination for a campaign.

    Legacy InviteCampaign target_chat_* fields remain as a denormalized cache for
    backwards compatibility. This record preserves platform-neutral identity and
    the connector data needed to resolve private Telegram communities reliably.
    """

    __tablename__ = "campaign_destinations"

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invite_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parsed_chat_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parsed_chats.id", ondelete="SET NULL"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    community_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    access_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_destination_campaign"),
        CheckConstraint(
            "NOT (platform = 'telegram' AND community_type IN ('channel', 'supergroup') "
            "AND COALESCE(username, '') = '' AND COALESCE(access_hash, '') = '')",
            name="ck_campaign_destination_resolvable_telegram",
        ),
        Index("ix_campaign_destinations_owner_platform", "owner_id", "platform"),
    )

    @property
    def connector_ref(self) -> str:
        if self.platform != "telegram":
            return self.external_id
        if self.username:
            return self.username if self.username.startswith("@") else f"@{self.username}"
        if self.community_type in {"channel", "supergroup"} and self.access_hash:
            return f"channel:{self.external_id}:{self.access_hash}"
        if self.community_type in {"group", "chat"}:
            return f"chat:{self.external_id}"
        return self.external_id


class CampaignDestinationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_campaign_from_community(
        self,
        *,
        owner_id: UUID,
        title: str,
        target_community_id: UUID,
        source_type: str = "parsed_list",
        source_chat_id: int | None = None,
        settings: dict | None = None,
        notes: str | None = None,
    ) -> tuple[InviteCampaign, CampaignDestination]:
        chat_result = await self.session.execute(
            select(ParsedChat).where(
                ParsedChat.id == target_community_id,
                ParsedChat.owner_id == owner_id,
            )
        )
        chat = chat_result.scalar_one_or_none()
        if chat is None:
            raise ValueError("Destination community not found")

        metadata = chat.extra_data or {}
        platform = str(metadata.get("platform") or "telegram").strip().lower()
        external_id = str(metadata.get("external_id") or abs(chat.chat_id))

        if platform == "telegram":
            if chat.chat_type not in {"group", "supergroup", "chat"}:
                raise ValueError(
                    "Telegram campaign destination must be a group or supergroup, not a broadcast channel"
                )
            if chat.chat_type == "supergroup" and not chat.username and not chat.access_hash:
                raise ValueError(
                    "Private Telegram supergroup is missing access data. Sync Telegram chats again before using it as a destination."
                )

        config = {
            "daily_limit_per_account": 30,
            "invite_delay_min": 45,
            "invite_delay_max": 180,
            "pause_after_every": 10,
            "pause_duration_min": 5,
            "pause_duration_max": 15,
            "warmup_enabled": True,
            "warmup_days": 3,
            "warmup_limit_factor": 0.2,
            "only_add_contacts": False,
            "add_to_contacts_first": True,
            "blacklist_usernames": None,
            "blacklist_user_ids": None,
        }
        if settings:
            config.update(settings)

        blacklist_usernames = config.pop("blacklist_usernames", None)
        blacklist_user_ids = config.pop("blacklist_user_ids", None)
        if isinstance(blacklist_usernames, list):
            blacklist_usernames = ",".join(str(item) for item in blacklist_usernames)
        if isinstance(blacklist_user_ids, list):
            blacklist_user_ids = ",".join(str(item) for item in blacklist_user_ids)

        campaign = InviteCampaign(
            owner_id=owner_id,
            title=title,
            status="draft",
            source_chat_id=source_chat_id,
            source_chat_title=None,
            source_type=source_type,
            target_chat_id=chat.chat_id,
            target_chat_title=chat.title,
            target_chat_username=chat.username,
            blacklist_usernames=blacklist_usernames,
            blacklist_user_ids=blacklist_user_ids,
            notes=notes,
            **config,
        )
        self.session.add(campaign)
        await self.session.flush()

        destination = CampaignDestination(
            owner_id=owner_id,
            campaign_id=campaign.id,
            parsed_chat_id=chat.id,
            platform=platform,
            external_id=external_id,
            username=chat.username,
            title=chat.title,
            community_type=chat.chat_type,
            access_hash=chat.access_hash,
        )
        self.session.add(destination)
        await self.session.commit()
        await self.session.refresh(campaign)
        await self.session.refresh(destination)
        return campaign, destination

    async def get_for_campaign(
        self,
        *,
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
