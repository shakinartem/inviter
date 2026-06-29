"""
Pydantic-схемы для ProxyCandidate.

Содержит:
- CandidateCreate        — схема для создания кандидата (внутренняя)
- CandidateResponse      — полный ответ (с маскировкой secret/password)
- CandidateListItem      — краткая схема для списков
- CandidateListResponse  — список с пагинацией
- MtprotoImportRequest   — запрос на импорт MTProto из текста
- MtprotoImportResult    — результат импорта
- TextImportRequest      — запрос на импорт обычных прокси из текста
- TextImportResult       — результат импорта обычных прокси
- BulkCheckRequest       — массовая проверка кандидатов
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.proxies.candidate_models import CANDIDATE_STATUS_TYPES

# ==================== Type aliases ====================

CandidateStatus = Literal["new", "checking", "alive", "dead", "approved", "rejected"]
CandidateSourceType = Literal["manual_text", "mtproto_text", "telegram_channel", "url_list", "local_adapter"]


def mask_secret(secret: str | None) -> str | None:
    """Замаскировать секрет: показать первые 4 и последние 4 символа."""
    if not secret:
        return None
    if len(secret) <= 8:
        return secret[:2] + "****" + secret[-2:]
    return secret[:4] + "****" + secret[-4:]


def mask_password(password: str | None) -> str | None:
    """Замаскировать пароль: показать первые 2 и последние 2 символа."""
    if not password:
        return None
    if len(password) <= 4:
        return "****"
    return password[:2] + "****" + password[-2:]


# ==================== Request schemas ====================


class MtprotoImportRequest(BaseModel):
    """Запрос на импорт MTProto-прокси из текста."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "tg://proxy?server=1.2.3.4&port=443&secret=abc123\nt.me/proxy?server=example.com&port=443&secret=xyz789",  # noqa: E501
                "source_name": "my_channel",
            }
        },
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Текст с MTProto-ссылками (можно несколько, через перенос строки)",
    )
    source_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Название источника (например, username канала)",
    )


class TextImportRequest(BaseModel):
    """Запрос на импорт обычных прокси из текста."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "socks5://user:pass@1.2.3.4:1080\nhttp://5.6.7.8:3128\n9.10.11.12:4153",
                "source_name": "my_list",
            }
        },
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Текст с прокси (построчно). Поддерживаемые форматы:\n"
                    "- ip:port\n- host:port\n"
                    "- socks5://host:port\n- socks5://user:pass@host:port\n"
                    "- http://host:port\n- http://user:pass@host:port",
    )
    source_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Название источника",
    )


class MtprotoImportResult(BaseModel):
    """Результат импорта MTProto-прокси из текста."""
    model_config = ConfigDict(from_attributes=True)

    found_count: int = Field(..., ge=0, description="Сколько всего найдено ссылок")
    imported_count: int = Field(..., ge=0, description="Сколько кандидатов создано")
    skipped_duplicates: int = Field(..., ge=0, description="Сколько пропущено дубликатов")
    invalid_count: int = Field(..., ge=0, description="Сколько некорректных ссылок")
    candidates: list["CandidateListItem"] = Field(
        default_factory=list,
        description="Созданные кандидаты",
    )


class TextImportResult(BaseModel):
    """Результат импорта обычных прокси из текста."""
    model_config = ConfigDict(from_attributes=True)

    found_count: int = Field(..., ge=0, description="Сколько всего найдено строк")
    imported_count: int = Field(..., ge=0, description="Сколько кандидатов создано")
    skipped_duplicates: int = Field(..., ge=0, description="Сколько пропущено дубликатов")
    invalid_count: int = Field(..., ge=0, description="Сколько некорректных строк")
    candidates: list["CandidateListItem"] = Field(
        default_factory=list,
        description="Созданные кандидаты",
    )


class BulkCheckRequest(BaseModel):
    """Запрос на массовую проверку кандидатов."""
    model_config = ConfigDict(from_attributes=True)

    ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Список ID кандидатов для проверки (макс. 50)",
    )


# ==================== Response schemas ====================


class CandidateResponse(BaseModel):
    """Полная информация о кандидате (secret/password маскируется)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proxy_type: str
    host: str
    port: int
    username: Optional[str] = Field(default=None, description="Имя пользователя")
    password: Optional[str] = Field(default=None, description="Пароль (маскируется)")
    secret: Optional[str] = Field(
        default=None,
        description="Секрет MTProto (маскируется в API)",
    )
    raw_value: Optional[str] = None
    source_type: str
    source_name: Optional[str] = None
    status: str
    score: int = 0
    latency_ms: Optional[float] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_masked_secrets(cls, candidate) -> "CandidateResponse":
        """Создать ответ с маскированными secret и password."""
        data = cls.model_validate(candidate, from_attributes=True)
        data.secret = mask_secret(data.secret)
        data.password = mask_password(data.password)
        return data


class CandidateListItem(BaseModel):
    """Краткая схема для списка кандидатов (secret/password маскируется)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proxy_type: str
    host: str
    port: int
    username: Optional[str] = Field(default=None, description="Имя пользователя")
    password: Optional[str] = Field(default=None, description="Пароль (замаскирован)")
    secret: Optional[str] = Field(
        default=None,
        description="Секрет (замаскирован)",
    )
    source_type: str
    source_name: Optional[str] = None
    status: str
    score: int = 0
    latency_ms: Optional[float] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_orm_with_masked_secrets(cls, candidate) -> "CandidateListItem":
        """Создать ответ с маскированными secret и password."""
        data = cls.model_validate(candidate, from_attributes=True)
        data.secret = mask_secret(data.secret)
        data.password = mask_password(data.password)
        return data


class CandidateListResponse(BaseModel):
    """Ответ со списком кандидатов + пагинация."""
    model_config = ConfigDict(from_attributes=True)

    items: list[CandidateListItem]
    total: int
    skip: int = 0
    limit: int = 50


CandidateListResponse.model_rebuild()
MtprotoImportResult.model_rebuild()
TextImportResult.model_rebuild()