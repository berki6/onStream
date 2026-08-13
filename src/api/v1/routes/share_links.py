"""Share link routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import share_link_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse
from src.schemas.share_link import ShareLinkCreate, ShareLinkExchange

router = APIRouter()


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    request: Request,
    body: ShareLinkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = share_link_service.create(
            db,
            current_user.id,
            upload_id=body.video_id,
            expires_in_seconds=body.expires_in_seconds,
            label=body.label,
            max_views=body.max_views,
            clip_start=body.clip_start,
            clip_end=body.clip_end,
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Share link created")


@router.get("/", response_model=APIResponse)
@router.get("", response_model=APIResponse)
def list_share_links(
    request: Request,
    video_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = share_link_service.list_for_video(
            db, current_user.id, upload_id=video_id
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Share links")


@router.delete("/{public_id}", response_model=APIResponse)
def revoke_share_link(
    request: Request,
    public_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = share_link_service.revoke(db, current_user.id, public_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Share link revoked")


@router.post("/{public_id}/peek", response_model=APIResponse)
def peek_share_link(
    request: Request,
    public_id: str,
    body: ShareLinkExchange,
    db: Session = Depends(get_db),
):
    """Public: validate share credentials without minting playback or burning max_views."""
    try:
        data = share_link_service.peek(db, public_id, body.token)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Share valid")


@router.post("/{public_id}/exchange", response_model=APIResponse)
def exchange_share_link(
    request: Request,
    public_id: str,
    body: ShareLinkExchange,
    db: Session = Depends(get_db),
):
    """Public: exchange share credentials for a short-lived playback token."""
    try:
        data = share_link_service.exchange(db, public_id, body.token)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Playback authorized")
