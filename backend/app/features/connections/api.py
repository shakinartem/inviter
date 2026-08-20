from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.connections.schemas import (
    ConnectionCheckResponse,
    ConnectionCreate,
    ConnectionCredentialsUpdate,
    ConnectionResponse,
    ConnectionUpdate,
    PlatformConnectionStatus,
)
from app.features.connections.service import ConnectionService


router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    platform: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=120),
    active_only: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ConnectionResponse]:
    service = ConnectionService(session)
    items = await service.list(
        user.id,
        platform=platform,
        search=search,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )
    return [ConnectionResponse(**service.serialize(item)) for item in items]


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionCreate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionResponse:
    service = ConnectionService(session)
    try:
        account = await service.create(user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConnectionResponse(**service.serialize(account))


@router.get("/platforms/{platform}", response_model=PlatformConnectionStatus)
async def platform_status(
    platform: str,
    _user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformConnectionStatus:
    service = ConnectionService(session)
    return PlatformConnectionStatus(**service.platform_status(platform))


@router.get("/{account_id}", response_model=ConnectionResponse)
async def get_connection(
    account_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionResponse:
    service = ConnectionService(session)
    account = await service.get(user.id, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return ConnectionResponse(**service.serialize(account))


@router.patch("/{account_id}", response_model=ConnectionResponse)
async def update_connection(
    account_id: UUID,
    payload: ConnectionUpdate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionResponse:
    service = ConnectionService(session)
    account = await service.update(user.id, account_id, payload)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return ConnectionResponse(**service.serialize(account))


@router.put("/{account_id}/credentials", response_model=ConnectionResponse)
async def replace_credentials(
    account_id: UUID,
    payload: ConnectionCredentialsUpdate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionResponse:
    service = ConnectionService(session)
    account = await service.replace_credentials(
        user.id,
        account_id,
        credentials=payload.credentials,
        auth_type=payload.auth_type,
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return ConnectionResponse(**service.serialize(account))


@router.post("/{account_id}/check", response_model=ConnectionCheckResponse)
async def check_connection(
    account_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionCheckResponse:
    service = ConnectionService(session)
    try:
        result = await service.check(user.id, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ConnectionCheckResponse(**result)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    account_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    service = ConnectionService(session)
    if not await service.delete(user.id, account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
