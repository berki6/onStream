"""HLS playback routes.

Path param ``video_id`` is the public ``upload_id`` (8-char alphanumeric).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.v1.deps import get_optional_user
from src.api.v1.responses import raise_app_error
from src.application import playback_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db

router = APIRouter()


def _bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def _origin(request: Request) -> str:
    return request.headers.get("Origin") or request.headers.get("Referer") or ""


@router.get("/{video_id}/master.m3u8")
async def master_playlist(
    video_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        from src.application.ids import validate_public_video_id
        from src.infrastructure.db.repositories import video_repository

        validate_public_video_id(video_id)
        video = video_repository.get_by_upload_id(db, video_id)
        if not video:
            raise AppError("Video not found", code="not_found", status_code=404)
        stream_token = playback_service.authorize_access(
            video,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        video = playback_service.get_ready_video(db, video_id)
        path, _ = playback_service.resolve_master(video)
        raw = path.read_text(encoding="utf-8", errors="ignore")
        body = playback_service.rewrite_playlist(raw, stream_token or token)
    except AppError as e:
        raise_app_error(e)
    return StreamingResponse(
        iter([body]), media_type="application/vnd.apple.mpegurl"
    )


@router.get("/{video_id}/{asset_path:path}")
async def playback_asset(
    video_id: str,
    asset_path: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        from src.application.ids import validate_public_video_id
        from src.infrastructure.db.repositories import video_repository

        validate_public_video_id(video_id)
        video = video_repository.get_by_upload_id(db, video_id)
        if not video:
            raise AppError("Video not found", code="not_found", status_code=404)
        stream_token = playback_service.authorize_access(
            video,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        video = playback_service.get_ready_video(db, video_id)
        path, safe = playback_service.resolve_asset(video, asset_path)
    except AppError as e:
        raise_app_error(e)

    if safe.endswith(".m3u8"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        body = playback_service.rewrite_playlist(raw, stream_token or token)
        return StreamingResponse(
            iter([body]), media_type="application/vnd.apple.mpegurl"
        )

    media_type = "video/MP2T" if safe.endswith(".ts") else "application/octet-stream"
    if safe.endswith(".jpg") or safe.endswith(".jpeg"):
        media_type = "image/jpeg"
    if safe.endswith(".vtt"):
        media_type = "text/vtt"

    def iterfile():
        with open(path, mode="rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                yield chunk

    return StreamingResponse(iterfile(), media_type=media_type)
