from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.campaigns.models import Campaign
    from app.features.inviter.models import InviteCampaign
    from app.features.parsed_chats.models import ParsedChat
    from app.features.proxies.models import Proxy


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)

    accounts: Mapped[list["Account"]] = relationship(back_populates="owner")
    proxies: Mapped[list["Proxy"]] = relationship(back_populates="owner")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="owner")
    parsed_chats: Mapped[list["ParsedChat"]] = relationship(back_populates="owner")
    invite_campaigns: Mapped[list["InviteCampaign"]] = relationship(back_populates="owner")