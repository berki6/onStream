"""Highlight catalog under /v1/videos/{id}/highlights and public GET."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user, get_optional_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import highlight_service, share_link_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse

router = APIRouter()


class HighlightCreate(BaseModel):
    start: Optional[float] = Field(None, ge=0)
    end: Optional[float] = Field(None, gt=0)
    title: Optional[str] = Field(None, max_length=120)
    from_chapters: bool = False


class HighlightShareCreate(BaseModel):
    expires_in_seconds: int = Field(86400, ge=60, le=60 * 60 * 24 * 90)
    max_views: Optional[int] = Field(None, ge=1, le=1_000_000)
    label: Optional[str] = Field(None, max_length=120)


@router.get("/videos/{video_id}/highlights", response_model=APIResponse)
def list_highlights(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        data = highlight_service.list_for_video(
            db, video_id, current_user.id if current_user else None
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlights")


@router.post(
    "/videos/{video_id}/highlights",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_highlight(
    request: Request,
    video_id: str,
    body: HighlightCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        if body.from_chapters:
            data = highlight_service.import_chapters(db, current_user.id, video_id)
            return api_ok(request, data, message="Highlights from chapters")
        if body.start is None or body.end is None:
            from src.application.error_codes import ErrorCode

            raise AppError(
                "start and end are required", code=ErrorCode.HIGHLIGHT_BAD_REQUEST
            )
        data = highlight_service.create(
            db,
            current_user.id,
            video_id,
            start=body.start,
            end=body.end,
            title=body.title,
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlight saved")


@router.delete(
    "/videos/{video_id}/highlights/{highlight_id}",
    response_model=APIResponse,
)
def delete_highlight(
    request: Request,
    video_id: str,
    highlight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = highlight_service.delete(
            db, current_user.id, video_id, highlight_id
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlight deleted")


@router.post(
    "/videos/{video_id}/highlights/{highlight_id}/tokens",
    response_model=APIResponse,
)
def highlight_token(
    request: Request,
    video_id: str,
    highlight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = highlight_service.issue_playback(
            db, current_user.id, video_id, highlight_id
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlight playback")


@router.post(
    "/videos/{video_id}/highlights/{highlight_id}/share",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def highlight_share(
    request: Request,
    video_id: str,
    highlight_id: str,
    body: Optional[HighlightShareCreate] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    payload = body or HighlightShareCreate()
    try:
        row, video = highlight_service.get_owned(
            db, current_user.id, video_id, highlight_id
        )
        data = share_link_service.create(
            db,
            current_user.id,
            upload_id=video.upload_id,
            expires_in_seconds=payload.expires_in_seconds,
            label=payload.label or row.title,
            max_views=payload.max_views,
            clip_start=row.start_seconds,
            clip_end=row.end_seconds,
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlight share created")


@router.get("/highlights/{highlight_id}", response_model=APIResponse)
def public_highlight(
    request: Request,
    highlight_id: str,
    db: Session = Depends(get_db),
):
    try:
        data = highlight_service.get_public(db, highlight_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Highlight")
