from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.session import get_db_session
from app.features.learning.webhook_schemas import (
    WebhookIngestResponse,
    WebhookSourceCreate,
    WebhookSourceResponse,
    WebhookSourceSecretResponse,
    WebhookSourceUpdate,
)
from app.features.learning.webhook_service import (
    OutcomeWebhookService,
    WebhookAuthenticationError,
    WebhookPayloadError,
    WebhookPolicyError,
    WebhookSourceNotFound,
)


router = APIRouter(tags=["learning", "outcome-webhooks"])


@router.post(
    "/learning/webhook-sources",
    response_model=WebhookSourceSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook_source(
    payload: WebhookSourceCreate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookSourceSecretResponse:
    try:
        source, signing_secret = await OutcomeWebhookService(session).create_source(user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WebhookSourceSecretResponse(
        source=WebhookSourceResponse.model_validate(source),
        signing_secret=signing_secret,
        webhook_path=f"/learning/webhooks/{source.id}/outcomes",
    )


@router.get("/learning/webhook-sources", response_model=list[WebhookSourceResponse])
async def list_webhook_sources(
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[WebhookSourceResponse]:
    items = await OutcomeWebhookService(session).list_sources(user.id)
    return [WebhookSourceResponse.model_validate(item) for item in items]


@router.patch(
    "/learning/webhook-sources/{source_id}",
    response_model=WebhookSourceResponse,
)
async def update_webhook_source(
    source_id: UUID,
    payload: WebhookSourceUpdate,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookSourceResponse:
    try:
        source = await OutcomeWebhookService(session).update_source(user.id, source_id, payload)
    except WebhookSourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WebhookSourceResponse.model_validate(source)


@router.post(
    "/learning/webhook-sources/{source_id}/rotate-secret",
    response_model=WebhookSourceSecretResponse,
)
async def rotate_webhook_secret(
    source_id: UUID,
    user=Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookSourceSecretResponse:
    try:
        source, signing_secret = await OutcomeWebhookService(session).rotate_secret(user.id, source_id)
    except WebhookSourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WebhookSourceSecretResponse(
        source=WebhookSourceResponse.model_validate(source),
        signing_secret=signing_secret,
        webhook_path=f"/learning/webhooks/{source.id}/outcomes",
    )


@router.post(
    "/learning/webhooks/{source_id}/outcomes",
    response_model=WebhookIngestResponse,
)
async def ingest_outcome_webhook(
    source_id: UUID,
    request: Request,
    x_qualive_timestamp: str = Header(..., alias="X-Qualive-Timestamp"),
    x_qualive_signature: str = Header(..., alias="X-Qualive-Signature"),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookIngestResponse:
    raw_body = await request.body()
    try:
        event, duplicate = await OutcomeWebhookService(session).ingest(
            source_id=source_id,
            timestamp_header=x_qualive_timestamp,
            signature_header=x_qualive_signature,
            raw_body=raw_body,
        )
    except WebhookSourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WebhookAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except WebhookPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WebhookPayloadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WebhookIngestResponse(
        accepted=True,
        duplicate=duplicate,
        outcome_event_id=event.id,
    )
