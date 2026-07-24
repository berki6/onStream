"""Live stream CRUD and MediaMTX auth webhook."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, api_page, raise_app_error
from src.application import live_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas.common import APIResponse, PaginatedResponse
from src.schemas.live import (
    LivePlaybackTokenCreate,
    LiveStreamCreate,
    LiveStreamCreateResponse,
    LiveStreamResponse,
    MediaMTXAuthRequest,
)

router = APIRouter()


def _auth_secret_from_request(request: Request, query_secret: Optional[str]) -> Optional[str]:
    return (
        request.headers.get("X-MediaMTX-Secret")
        or request.headers.get("X-Auth-Secret")
        or query_secret
    )


@router.post("/mediamtx-auth")
@router.get("/mediamtx-auth")
async def mediamtx_auth(
    request: Request,
    db: Session = Depends(get_db),
    secret: Optional[str] = Query(None),
):
    """
    MediaMTX HTTP auth callback.

    Returns 200 on success, 401 on failure (no user JWT).
    """
    auth_secret = _auth_secret_from_request(request, secret)
    try:
        if request.method == "GET":
            path = request.query_params.get("path", "")
            action = request.query_params.get("action", "publish")
        else:
            raw = await request.json()
            body = MediaMTXAuthRequest.model_validate(raw)
            path = body.path
            action = body.action

        live_service.authorize_publish(
            db, path=path, action=action, auth_secret=auth_secret
        )
    except AppError:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    return Response(status_code=status.HTTP_200_OK)


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_live_stream(
    request: Request,
    body: LiveStreamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = live_service.create_stream(
            db, current_user.id, title=body.title, is_public=body.is_public
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        LiveStreamCreateResponse.model_validate(data),
        message="Live stream created",
    )


@router.get("/", response_model=PaginatedResponse)
def list_live_streams(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        rows, total = live_service.list_streams(
            db, current_user.id, skip=skip, limit=limit
        )
    except AppError as e:
        raise_app_error(e)
    return api_page(
        request,
        [LiveStreamResponse.model_validate(r) for r in rows],
        total_count=total,
        skip=skip,
        limit=limit,
        message=f"Retrieved {len(rows)} live streams",
    )


@router.get("/{stream_id}", response_model=APIResponse)
def get_live_stream(
    request: Request,
    stream_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = live_service.get_stream(db, stream_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        LiveStreamResponse.model_validate(data),
        message="Live stream retrieved",
    )


@router.get("/{stream_id}/health", response_model=APIResponse)
def get_live_stream_health(
    request: Request,
    stream_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = live_service.get_stream_health(db, stream_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Live stream health")


@router.delete("/{stream_id}", response_model=APIResponse)
def delete_live_stream(
    request: Request,
    stream_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = live_service.delete_stream(db, stream_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        LiveStreamResponse.model_validate(data),
        message="Live stream revoked",
    )


@router.post("/{stream_id}/tokens", response_model=APIResponse)
def issue_live_playback_token(
    request: Request,
    stream_id: str,
    body: Optional[LivePlaybackTokenCreate] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    payload = body or LivePlaybackTokenCreate()
    try:
        data = live_service.issue_live_token(
            db, stream_id, current_user.id, expires_in=payload.expires_in
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Playback token issued")
