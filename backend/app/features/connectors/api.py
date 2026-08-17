from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_active_user
from app.features.connectors.defaults import register_default_connectors
from app.features.connectors.registry import connector_registry


router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
async def list_connectors(_user=Depends(get_current_active_user)) -> list[dict]:
    register_default_connectors()
    return connector_registry.list()


@router.get("/{platform}")
async def get_connector(platform: str, _user=Depends(get_current_active_user)) -> dict:
    register_default_connectors()
    try:
        return connector_registry.get(platform).describe()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
