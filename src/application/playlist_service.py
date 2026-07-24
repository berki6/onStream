"""Playlist application service (no FastAPI).

When nesting videos, ``upload_id`` / path video ids are the public 8-char ids.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.core.config import settings
from src.infrastructure.db.repositories import playlist_repository, video_repository
from src.schemas.playlist import PlaylistCreate, PlaylistVideoCreate

MAX_TITLE_LENGTH = 100


def create_playlist(db: Session, user_id: int, playlist: PlaylistCreate):
    if len(playlist.name) > MAX_TITLE_LENGTH:
        raise AppError(
            f"Title must be {MAX_TITLE_LENGTH} characters or less",
            code=ErrorCode.PLAYLIST_BAD_REQUEST,
            status_code=400,
        )
    existing_playlists, _ = playlist_repository.list_by_user(db, user_id)
    if any(p.name == playlist.name for p in existing_playlists):
        raise AppError(
            "Playlist with this title already exists",
            code=ErrorCode.PLAYLIST_CONFLICT,
            status_code=400,
        )
    return playlist_repository.create(db, playlist, user_id)


def list_playlists(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> Tuple[list, int]:
    if skip < 0:
        raise AppError(
            "Skip parameter must be non-negative", code=ErrorCode.PLAYLIST_BAD_REQUEST, status_code=400
        )
    if limit < 1 or limit > settings.MAX_LIST_LIMIT:
        raise AppError(
            f"Limit must be between 1 and {settings.MAX_LIST_LIMIT}",
            code=ErrorCode.PLAYLIST_BAD_REQUEST,
            status_code=400,
        )
    return playlist_repository.list_by_user(db, user_id, skip=skip, limit=limit)


def get_playlist(db: Session, playlist_id: int, user_id: int):
    playlist = playlist_repository.get_by_id(db, playlist_id)
    if not playlist:
        raise AppError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND, status_code=404)
    if playlist.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.PLAYLIST_FORBIDDEN, status_code=403)
    return playlist


def delete_playlist(db: Session, playlist_id: int, user_id: int) -> None:
    get_playlist(db, playlist_id, user_id)
    playlist_repository.delete(db, playlist_id)


def add_video(
    db: Session,
    playlist_id: int,
    video_id: str,
    user_id: int,
    video_data: PlaylistVideoCreate,
) -> Dict[str, Any]:
    """``video_id`` is the public upload_id."""
    validate_public_video_id(video_id)
    get_playlist(db, playlist_id, user_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND, status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.PLAYLIST_FORBIDDEN, status_code=403)
    result = playlist_repository.add_video(db, playlist_id, video.id, video_data.position)
    if result is None:
        raise AppError(
            "Video already in playlist", code=ErrorCode.PLAYLIST_BAD_REQUEST, status_code=400
        )
    return {
        "playlist_id": playlist_id,
        "video_upload_id": video_id,
        "position": video_data.position,
    }


def remove_video(
    db: Session, playlist_id: int, video_id: str, user_id: int
) -> None:
    validate_public_video_id(video_id)
    get_playlist(db, playlist_id, user_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND, status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.PLAYLIST_FORBIDDEN, status_code=403)
    result = playlist_repository.remove_video(db, playlist_id, video.id)
    if not result:
        raise AppError("Video not in playlist", code=ErrorCode.PLAYLIST_NOT_FOUND, status_code=404)


def list_videos(db: Session, playlist_id: int, user_id: int) -> List[Dict[str, Any]]:
    get_playlist(db, playlist_id, user_id)
    playlist_videos = playlist_repository.get_videos(db, playlist_id)
    videos = []
    for pv in playlist_videos:
        video = video_repository.get_by_id(db, pv.video_id)
        if video:
            videos.append(
                {
                    "upload_id": video.upload_id,
                    "title": video.title,
                    "position": pv.position,
                }
            )
    return videos


def update_video_position(
    db: Session,
    playlist_id: int,
    video_id: str,
    user_id: int,
    video_data: PlaylistVideoCreate,
) -> Dict[str, Any]:
    validate_public_video_id(video_id)
    get_playlist(db, playlist_id, user_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND, status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.PLAYLIST_FORBIDDEN, status_code=403)
    result = playlist_repository.update_video_position(
        db, playlist_id, video.id, video_data.position
    )
    if not result:
        raise AppError("Video not in playlist", code=ErrorCode.PLAYLIST_BAD_REQUEST, status_code=400)
    return {
        "playlist_id": playlist_id,
        "video_upload_id": video_id,
        "position": video_data.position,
    }
