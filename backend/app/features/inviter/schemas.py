from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


class InviteSettings(BaseModel):
    """
    Настройки безопасности и поведения кампании инвайтинга.
    Все параметры можно переопределить при запуске кампании.
    """
    daily_limit_per_account: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Максимальное количество инвайтов в день на один аккаунт"
    )
    reserve_capacity_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=50.0,
        description="Доля безопасной account-capacity, оставляемая свободной для failover"
    )
    invite_delay_min: int = Field(
        default=45,
        ge=10,
        le=300,
        description="Минимальная задержка между инвайтами в секундах"
    )
    invite_delay_max: int = Field(
        default=180,
        ge=10,
        le=600,
        description="Максимальная задержка между инвайтами в секундах"
    )
    pause_after_every: int = Field(
        default=10,
        ge=1,
        le=50,
        description="После скольких инвайтов делать паузу"
    )
    pause_duration_min: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Минимальная длительность паузы в минутах"
    )
    pause_duration_max: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Максимальная длительность паузы в минутах"
    )
    warmup_enabled: bool = Field(
        default=True,
        description="Включить прогрев аккаунтов"
    )
    warmup_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Количество дней для периода прогрева"
    )
    warmup_limit_factor: float = Field(
        default=0.2,
        ge=0.01,
        le=1.0,
        description="Коэффициент снижения лимита в период прогрева (от 0.01 до 1.0)"
    )
    only_add_contacts: bool = Field(
        default=False,
        description="Режим только добавления в контакты без приглашения в чат"
    )
    add_to_contacts_first: bool = Field(
        default=True,
        description="Сначала добавлять в контакты, затем приглашать в чат"
    )
    blacklist_usernames: List[str] = Field(
        default_factory=list,
        description="Список username для блокировки (не приглашать)"
    )
    blacklist_user_ids: List[int] = Field(
        default_factory=list,
        description="Список user_id для блокировки (не приглашать)"
    )

    @field_validator('invite_delay_max')
    @classmethod
    def check_invite_delay_max(cls, v: int, info) -> int:
        if 'invite_delay_min' in info.data and v <= info.data['invite_delay_min']:
            raise ValueError('invite_delay_max must be greater than invite_delay_min')
        return v

    @field_validator('pause_duration_max')
    @classmethod
    def check_pause_duration_max(cls, v: int, info) -> int:
        if 'pause_duration_min' in info.data and v <= info.data['pause_duration_min']:
            raise ValueError('pause_duration_max must be greater than pause_duration_min')
        return v


class InviteCampaignCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, max_length=160, description="Название кампании")
    target_chat_id: int = Field(..., description="ID целевого чата/канала, куда приглашать пользователей")
    target_chat_title: Optional[str] = Field(default=None, max_length=255)
    target_chat_username: Optional[str] = Field(default=None, max_length=255)
    source_chat_id: Optional[int] = None
    source_chat_title: Optional[str] = Field(default=None, max_length=255)
    source_type: Literal["chat", "parsed_list", "uploaded_list"] = "chat"
    notes: Optional[str] = None
    settings: InviteSettings = Field(default_factory=InviteSettings)


class InviteCampaignUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    target_chat_id: Optional[int] = None
    target_chat_title: Optional[str] = Field(default=None, max_length=255)
    target_chat_username: Optional[str] = Field(default=None, max_length=255)
    source_chat_id: Optional[int] = None
    source_chat_title: Optional[str] = Field(default=None, max_length=255)
    source_type: Optional[Literal["chat", "parsed_list", "uploaded_list"]] = None
    notes: Optional[str] = None
    status: Optional[Literal["draft", "active", "paused", "completed", "failed"]] = None
    settings: Optional[InviteSettings] = None


class InviteCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    status: Literal["draft", "active", "paused", "completed", "failed"]
    source_chat_id: Optional[int]
    source_chat_title: Optional[str]
    source_type: Literal["chat", "parsed_list", "uploaded_list"]
    target_chat_id: int
    target_chat_title: Optional[str]
    target_chat_username: Optional[str]
    daily_limit_per_account: int
    reserve_capacity_percentage: float
    invite_delay_min: int
    invite_delay_max: int
    pause_after_every: int
    pause_duration_min: int
    pause_duration_max: int
    warmup_enabled: bool
    warmup_days: int
    warmup_limit_factor: float
    only_add_contacts: bool
    add_to_contacts_first: bool
    blacklist_usernames: List[str]
    blacklist_user_ids: List[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    tasks_count: Optional[int] = None
    completed_tasks_count: Optional[int] = None
    failed_tasks_count: Optional[int] = None
    floodwait_tasks_count: Optional[int] = None
    success_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class InviteCampaignList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: Literal["draft", "active", "paused", "completed", "failed"]
    target_chat_title: Optional[str]
    target_chat_username: Optional[str]
    tasks_count: int
    completed_tasks_count: int
    success_rate: float
    created_at: datetime
    updated_at: datetime


class InviteTaskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID
    account_id: UUID
    proxy_id: Optional[UUID] = None
    target_user_id: int
    target_username: Optional[str] = None


class InviteTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    account_id: UUID
    proxy_id: Optional[UUID]
    target_user_id: int
    target_username: Optional[str]
    status: Literal["pending", "processing", "success", "failed", "floodwait", "paused"]
    attempts: int
    max_attempts: int
    next_attempt_at: Optional[datetime]
    error_code: Optional[str]
    error_message: Optional[str]
    invited_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class InviteLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invite_task_id: UUID
    action: Literal["add_contact", "invite_to_chat", "check_user"]
    success: bool
    error_code: Optional[str]
    error_message: Optional[str]
    created_at: datetime


class CampaignStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID
    title: str
    status: Literal["draft", "active", "paused", "completed", "failed"]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    floodwait_tasks: int
    success_rate: float
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    invites_today: int
    active_accounts: int


class InviteCampaignFilter(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Optional[Literal["draft", "active", "paused", "completed", "failed"]] = None
    owner_id: Optional[UUID] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    target_chat_id: Optional[int] = None
    search: Optional[str] = None


class StartCampaignRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID
    override_settings: Optional[InviteSettings] = None
    max_parallel_tasks: Optional[int] = Field(default=None, ge=1, le=50)
