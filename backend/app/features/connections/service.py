from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.credentials import CredentialVault, credential_vault
from app.features.accounts.models import Account
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import ConnectorRegistry, connector_registry
from app.features.connections.schemas import ConnectionCreate, ConnectionUpdate


@dataclass(slots=True)
class ConnectorAccountContext:
    """Expose decrypted credentials only for the lifetime of a connector call."""

    account: Account
    credentials: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        return getattr(self.account, name)


class ConnectionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: ConnectorRegistry | None = None,
        vault: CredentialVault | None = None,
    ) -> None:
        self.session = session
        register_default_connectors()
        self.registry = registry or connector_registry
        self.vault = vault or credential_vault

    async def create(self, owner_id: UUID, payload: ConnectionCreate) -> Account:
        platform = payload.platform.strip().lower()
        auth_type = payload.auth_type.strip().lower()

        if payload.external_account_id:
            existing = await self.session.execute(
                select(Account.id).where(
                    Account.owner_id == owner_id,
                    Account.platform == platform,
                    Account.external_account_id == payload.external_account_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("This messenger account is already connected")

        capabilities = self._capabilities(platform)
        account = Account(
            owner_id=owner_id,
            platform=platform,
            external_account_id=payload.external_account_id,
            auth_type=auth_type,
            credential_payload_encrypted=self.vault.encrypt(payload.credentials),
            capabilities=capabilities,
            health_score=100.0 if self.registry.supports(platform) else 50.0,
            label=payload.label,
            proxy_id=payload.proxy_id,
            notes=payload.notes,
            extra_data=payload.metadata,
            # Transitional compatibility with the legacy Account API. The value is
            # not used by non-Telegram connectors.
            session_name=f"conn_{platform}_{secrets.token_hex(8)}",
            status="idle",
            is_active=True,
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def get(self, owner_id: UUID, account_id: UUID) -> Account | None:
        result = await self.session.execute(
            select(Account).where(
                Account.id == account_id,
                Account.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        owner_id: UUID,
        *,
        platform: str | None = None,
        search: str | None = None,
        active_only: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Account]:
        stmt = select(Account).where(Account.owner_id == owner_id)
        if platform:
            stmt = stmt.where(Account.platform == platform.strip().lower())
        if active_only is not None:
            stmt = stmt.where(Account.is_active == active_only)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Account.label.ilike(term),
                    Account.username.ilike(term),
                    Account.external_account_id.ilike(term),
                )
            )
        result = await self.session.execute(
            stmt.order_by(Account.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self,
        owner_id: UUID,
        account_id: UUID,
        payload: ConnectionUpdate,
    ) -> Account | None:
        account = await self.get(owner_id, account_id)
        if account is None:
            return None
        updates = payload.model_dump(exclude_unset=True)
        metadata = updates.pop("metadata", None) if "metadata" in updates else None
        for key, value in updates.items():
            setattr(account, key, value)
        if "metadata" in payload.model_fields_set:
            account.extra_data = metadata
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def replace_credentials(
        self,
        owner_id: UUID,
        account_id: UUID,
        *,
        credentials: dict[str, Any],
        auth_type: str | None = None,
    ) -> Account | None:
        account = await self.get(owner_id, account_id)
        if account is None:
            return None
        account.credential_payload_encrypted = self.vault.encrypt(credentials)
        if auth_type:
            account.auth_type = auth_type.strip().lower()
        account.status = "idle"
        account.status_message = "Credentials updated; connection check required"
        account.last_checked_at = None
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def check(self, owner_id: UUID, account_id: UUID) -> dict[str, Any]:
        account = await self.get(owner_id, account_id)
        if account is None:
            raise ValueError("Connection not found")
        if not self.registry.supports(account.platform):
            account.status = "idle"
            account.status_message = f"Connector for {account.platform} is not installed"
            account.health_score = 50.0
            account.last_checked_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {
                "account_id": account.id,
                "platform": account.platform,
                "ok": False,
                "connector_available": False,
                "status": account.status,
                "external_account_id": account.external_account_id,
                "username": account.username,
                "error": account.status_message,
                "capabilities": {},
            }

        connector = self.registry.get(account.platform)
        context = ConnectorAccountContext(
            account=account,
            credentials=self.vault.decrypt(account.credential_payload_encrypted),
        )
        try:
            result = await connector.check_account(context)
        except Exception as exc:
            account.status = "error"
            account.status_message = str(exc)[:500]
            account.health_score = max(account.health_score - 20.0, 0.0)
            account.last_checked_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {
                "account_id": account.id,
                "platform": account.platform,
                "ok": False,
                "connector_available": True,
                "status": account.status,
                "external_account_id": account.external_account_id,
                "username": account.username,
                "error": account.status_message,
                "capabilities": account.capabilities or connector.capabilities.as_dict(),
            }

        resolved_capabilities = result.get("capabilities")
        if not isinstance(resolved_capabilities, dict):
            resolved_capabilities = connector.capabilities.as_dict()
        else:
            resolved_capabilities = {
                str(key): bool(value) for key, value in resolved_capabilities.items()
            }

        account.external_account_id = str(
            result.get("external_account_id") or account.external_account_id or ""
        ) or None
        account.username = result.get("username") or account.username
        account.first_name = result.get("first_name") or account.first_name
        account.last_name = result.get("last_name") or account.last_name
        account.capabilities = resolved_capabilities
        account.status = "active" if result.get("ok") else "error"
        account.status_message = None if result.get("ok") else str(result.get("error") or "Check failed")[:500]
        account.health_score = 100.0 if result.get("ok") else max(account.health_score - 10.0, 0.0)
        account.last_checked_at = datetime.now(timezone.utc)
        account.last_seen_at = account.last_checked_at if result.get("ok") else account.last_seen_at
        await self.session.commit()
        await self.session.refresh(account)

        return {
            "account_id": account.id,
            "platform": account.platform,
            "ok": bool(result.get("ok")),
            "connector_available": True,
            "status": account.status,
            "external_account_id": account.external_account_id,
            "username": account.username,
            "error": account.status_message,
            "capabilities": resolved_capabilities,
        }

    async def delete(self, owner_id: UUID, account_id: UUID) -> bool:
        account = await self.get(owner_id, account_id)
        if account is None:
            return False
        await self.session.delete(account)
        await self.session.commit()
        return True

    def serialize(self, account: Account) -> dict[str, Any]:
        return {
            "id": account.id,
            "owner_id": account.owner_id,
            "platform": account.platform,
            "external_account_id": account.external_account_id,
            "label": account.label,
            "auth_type": account.auth_type,
            "username": account.username,
            "first_name": account.first_name,
            "last_name": account.last_name,
            "status": account.status,
            "status_message": account.status_message,
            "is_active": account.is_active,
            "capabilities": account.capabilities,
            "health_score": account.health_score,
            "proxy_id": account.proxy_id,
            "last_seen_at": account.last_seen_at,
            "last_used_at": account.last_used_at,
            "last_checked_at": account.last_checked_at,
            "metadata": account.extra_data,
            "notes": account.notes,
            "has_credentials": bool(account.credential_payload_encrypted),
            "connector_available": self.registry.supports(account.platform),
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def platform_status(self, platform: str) -> dict[str, Any]:
        key = platform.strip().lower()
        if not self.registry.supports(key):
            return {"platform": key, "connector_available": False, "capabilities": {}}
        connector = self.registry.get(key)
        return {
            "platform": key,
            "connector_available": True,
            "capabilities": connector.capabilities.as_dict(),
        }

    def _capabilities(self, platform: str) -> dict[str, bool]:
        if not self.registry.supports(platform):
            return {}
        return self.registry.get(platform).capabilities.as_dict()
