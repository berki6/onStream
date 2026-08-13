"""Public RSS feeds (unauthenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.api.v1.responses import raise_app_error
from src.application import feed_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db

router = APIRouter()


@router.get("/{username}/videos.rss")
def user_videos_feed(username: str, db: Session = Depends(get_db)):
    try:
        xml = feed_service.user_videos_rss(db, username)
    except AppError as e:
        raise_app_error(e)
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get("/{username}/playlists/{playlist_id}.rss")
def playlist_feed(
    username: str, playlist_id: int, db: Session = Depends(get_db)
):
    try:
        xml = feed_service.playlist_rss(db, username, playlist_id)
    except AppError as e:
        raise_app_error(e)
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
