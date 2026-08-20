from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialVault:
    """Small self-hosted encrypted credential store backed by the accounts table.

    The application secret is expanded into a Fernet key. Ciphertext is safe to
    persist in Postgres, while decrypted values should only exist inside a
    connector operation. A dedicated KMS/Vault can replace this class later
    without changing the Account API contract.
    """

    VERSION = "v1"
    INSECURE_DEFAULTS = {"", "change-me", "changeme", "secret"}

    def __init__(self, secret: str | None = None) -> None:
        self._source_secret = secret or settings.secret
        source = self._source_secret.encode("utf-8")
        digest = hashlib.sha256(source).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    @property
    def is_securely_configured(self) -> bool:
        normalized = self._source_secret.strip().lower()
        return normalized not in self.INSECURE_DEFAULTS and len(self._source_secret) >= 24

    def require_secure_configuration(self) -> None:
        if not self.is_securely_configured:
            raise ValueError(
                "APP_SECRET must be changed to a strong value (at least 24 characters) "
                "before storing messenger credentials"
            )

    def encrypt(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        self.require_secure_configuration()
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        token = self._fernet.encrypt(raw).decode("ascii")
        return f"{self.VERSION}:{token}"

    def decrypt(self, ciphertext: str | None) -> dict[str, Any]:
        if not ciphertext:
            return {}
        try:
            version, token = ciphertext.split(":", 1)
        except ValueError as exc:
            raise ValueError("Malformed encrypted credential payload") from exc
        if version != self.VERSION:
            raise ValueError(f"Unsupported credential payload version: {version}")
        try:
            raw = self._fernet.decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt account credentials") from exc
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Credential payload must decode to an object")
        return decoded


credential_vault = CredentialVault()
