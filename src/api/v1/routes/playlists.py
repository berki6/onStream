from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, api_page, raise_app_error
from src.application import playlist_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import (
    APIResponse,
    PaginatedResponse,
    Playlist,
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistVideoCreate,
)

router = APIRouter()


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_playlist(
    request: Request,
    playlist: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        db_playlist = playlist_service.create_playlist(db, current_user.id, playlist)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        Playlist.model_validate(db_playlist),
        message="Playlist created successfully",
    )


@router.get("/", response_model=PaginatedResponse)
def list_playlists(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    contains_video: Optional[str] = Query(
        None,
        description="Public upload_id — each row includes contains_video true/false",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        playlists, total_count = playlist_service.list_playlists(
            db, current_user.id, skip=skip, limit=limit
        )
        member_ids = None
        if contains_video:
            member_ids = playlist_service.playlist_ids_containing_upload(
                db, current_user.id, contains_video
            )
    except AppError as e:
        raise_app_error(e)
    items = []
    for p in playlists:
        row = Playlist.model_validate(p)
        if member_ids is not None:
            row = row.model_copy(update={"contains_video": p.id in member_ids})
        items.append(row)
    return api_page(
        request,
        items,
        total_count=total_count,
        skip=skip,
        limit=limit,
        message=f"Retrieved {len(playlists)} playlists",
    )


@router.get("/public/{playlist_id}", response_model=APIResponse)
def get_public_playlist(
    request: Request,
    playlist_id: int,
    db: Session = Depends(get_db),
):
    try:
        data = playlist_service.get_public_playlist(db, playlist_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Public playlist")


@router.get("/{playlist_id}", response_model=APIResponse)
def get_playlist(
    request: Request,
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        playlist = playlist_service.get_playlist(db, playlist_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        Playlist.model_validate(playlist),
        message="Playlist retrieved successfully",
    )


@router.patch("/{playlist_id}", response_model=APIResponse)
def update_playlist(
    request: Request,
    playlist_id: int,
    body: PlaylistUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        playlist = playlist_service.update_playlist(
            db, playlist_id, current_user.id, body
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        Playlist.model_validate(playlist),
        message="Playlist updated",
    )


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        playlist_service.delete_playlist(db, playlist_id, current_user.id)
    except AppError as e:
        raise_app_error(e)


@router.post(
    "/{playlist_id}/videos/{video_id}",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_video_to_playlist(
    request: Request,
    playlist_id: int,
    video_id: str,
    video_data: PlaylistVideoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        data = playlist_service.add_video(
            db, playlist_id, video_id, current_user.id, video_data
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Video added to playlist successfully")


@router.delete(
    "/{playlist_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_video_from_playlist(
    playlist_id: int,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        playlist_service.remove_video(db, playlist_id, video_id, current_user.id)
    except AppError as e:
        raise_app_error(e)


@router.get("/{playlist_id}/videos", response_model=APIResponse)
def get_playlist_videos(
    request: Request,
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        videos = playlist_service.list_videos(db, playlist_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request, videos, message=f"Retrieved {len(videos)} videos from playlist"
    )


@router.put("/{playlist_id}/videos/{video_id}", response_model=APIResponse)
def update_video_position(
    request: Request,
    playlist_id: int,
    video_id: str,
    video_data: PlaylistVideoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        data = playlist_service.update_video_position(
            db, playlist_id, video_id, current_user.id, video_data
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Video position updated successfully")
