"""Live HLS playback routes under /playback/live/{stream_id}/..."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.v1.deps import get_optional_user
from src.api.v1.responses import raise_app_error
from src.application import live_service, playback_service
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


@router.get("/{stream_id}/master.m3u8")
async def live_master_playlist(
    stream_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        path = live_service.resolve_master(stream)
        raw = path.read_text(encoding="utf-8", errors="ignore")
        body = playback_service.rewrite_playlist(raw, stream_token or token)
    except AppError as e:
        raise_app_error(e)
    return StreamingResponse(
        iter([body]), media_type="application/vnd.apple.mpegurl"
    )


@router.get("/{stream_id}/{asset_path:path}")
async def live_playback_asset(
    stream_id: str,
    asset_path: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        path, safe = live_service.resolve_asset(stream, asset_path)
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
