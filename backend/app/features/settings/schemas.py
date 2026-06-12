from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    id: UUID
    language: Literal["ru", "en"] = Field(..., description="Interface language: ru or en")
    site_name: Optional[str] = Field(None, description="Site display name")
    logo_path: Optional[str] = Field(None, description="Relative path to logo file")
    help_text: Optional[str] = Field(None, description="Help / instruction text")
    system_config: Optional[dict[str, Any]] = Field(None, description="System settings JSON")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    language: Optional[Literal["ru", "en"]] = Field(None, description="Interface language: ru or en")
    site_name: Optional[str] = Field(None, description="Site display name")
    help_text: Optional[str] = Field(None, description="Help / instruction text")
    system_config: Optional[dict[str, Any]] = Field(None, description="System settings JSON")


class LogoUploadResponse(BaseModel):
    logo_path: Optional[str] = None
    message: str
