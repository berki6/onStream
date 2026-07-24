"""Video routes.

Path param ``video_id`` is the public ``upload_id`` (8-char alphanumeric).
DB column remains ``upload_id``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, api_page, raise_app_error
from src.application import playback_service, video_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.core.logger import get_logger
from src.schemas import (
    APIResponse,
    PaginatedResponse,
    PlaybackTokenCreate,
    Video,
    VideoUpdate,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Multipart upload convenience endpoint."""
    try:
        video = video_service.create_multipart_upload(
            db,
            current_user.id,
            filename=file.filename or "",
            content_type=file.content_type,
            file_size=file.size,
            title=title,
            description=description,
            file_obj=file.file,
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        Video.model_validate(video),
        message="Video uploaded successfully and queued for processing",
    )


@router.get("/", response_model=PaginatedResponse)
def list_videos(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        videos, total_count = video_service.list_videos(
            db, current_user.id, skip=skip, limit=limit
        )
    except AppError as e:
        raise_app_error(e)
    return api_page(
        request,
        [Video.model_validate(v) for v in videos],
        total_count=total_count,
        skip=skip,
        limit=limit,
        message=f"Retrieved {len(videos)} videos",
    )


@router.get("/{video_id}", response_model=APIResponse)
def get_video(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        video = video_service.get_video(db, video_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request, Video.model_validate(video), message="Video retrieved successfully"
    )


@router.patch("/{video_id}", response_model=APIResponse)
def update_video(
    request: Request,
    video_id: str,
    body: VideoUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        video = video_service.update_video(db, video_id, current_user.id, body)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, Video.model_validate(video), message="Video updated")


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        video_service.delete_video(db, video_id, current_user.id)
    except AppError as e:
        raise_app_error(e)


@router.post("/{video_id}/tokens", response_model=APIResponse)
def create_playback_token(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    body: Optional[PlaybackTokenCreate] = Body(None),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    payload = body or PlaybackTokenCreate()
    try:
        data = playback_service.issue_token(
            db, video_id, current_user.id, expires_in=payload.expires_in
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Playback token issued")


@router.get("/{video_id}/chapters", response_model=APIResponse)
def get_video_chapters(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return AI-generated chapters for a video."""
    from src.application import caption_service

    try:
        chapters = caption_service.get_chapters(db, video_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, {"chapters": chapters}, message="Chapters retrieved")
