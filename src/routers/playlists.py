from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_db
from src.core.logger import get_logger
from src.schema import schemas
from src.services import crud

router = APIRouter()

logger = get_logger(__name__)

MAX_TITLE_LENGTH = 100


@router.post(
    "/", response_model=schemas.APIResponse, status_code=status.HTTP_201_CREATED
)
def create_playlist(
    request: Request,
    playlist: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new playlist."""
    # Validate title length
    if len(playlist.name) > MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Title must be {MAX_TITLE_LENGTH} characters or less",
        )

    # Check for duplicate title for this user
    existing_playlists = crud.get_playlists_by_user(db, current_user.id)
    if any(p.name == playlist.name for p in existing_playlists):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playlist with this title already exists",
        )

    try:
        db_playlist = crud.create_playlist(db, playlist, current_user.id)
        logger.info(
            f"User '{current_user.username}' created playlist '{playlist.name}'"
        )
        return schemas.APIResponse(
            data=db_playlist,
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Playlist created successfully",
        )
    except Exception as e:
        logger.error(
            f"Failed to create playlist for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create playlist",
        )


@router.get("/", response_model=schemas.PaginatedResponse)
def list_playlists(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List user's playlists."""
    # Validate query parameters
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip parameter must be non-negative",
        )
    if limit < 1 or limit > settings.MAX_LIST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limit must be between 1 and {settings.MAX_LIST_LIMIT}",
        )

    try:
        playlists, total_count = crud.get_playlists_by_user(
            db, current_user.id, skip=skip, limit=limit
        )
        logger.info(
            f"User '{current_user.username}' listed playlists: {len(playlists)} playlists"
        )
        return schemas.PaginatedResponse(
            data=playlists,
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message=f"Retrieved {len(playlists)} playlists",
            pagination={
                "total_count": total_count,
                "page": (skip // limit) + 1,
                "per_page": limit,
                "has_more": skip + limit < total_count,
            },
        )
    except Exception as e:
        logger.error(
            f"Failed to list playlists for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve playlists",
        )


@router.get("/{playlist_id}", response_model=schemas.APIResponse)
def get_playlist(
    request: Request,
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific playlist."""
    try:
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        logger.info(
            f"User '{current_user.username}' accessed playlist ID {playlist_id}"
        )
        return schemas.APIResponse(
            data=playlist,
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Playlist retrieved successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve playlist",
        )


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a playlist."""
    try:
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        crud.delete_playlist(db, playlist_id)
        logger.info(f"User '{current_user.username}' deleted playlist ID {playlist_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete playlist",
        )


@router.post(
    "/{playlist_id}/videos/{upload_id}",
    response_model=schemas.APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_video_to_playlist(
    request: Request,
    playlist_id: int,
    upload_id: str,
    video_data: schemas.PlaylistVideoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add a video to a playlist."""
    # Validate upload_id format
    if not upload_id or len(upload_id) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    try:
        # Check playlist ownership
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Check video ownership
        video = crud.get_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Add video to playlist
        result = crud.add_video_to_playlist(
            db, playlist_id, video.id, video_data.position
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video already in playlist",
            )

        logger.info(
            f"User '{current_user.username}' added video {upload_id} to playlist {playlist_id}"
        )
        return schemas.APIResponse(
            data={
                "playlist_id": playlist_id,
                "video_upload_id": upload_id,
                "position": video_data.position,
            },
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Video added to playlist successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to add video {upload_id} to playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add video to playlist",
        )


@router.delete(
    "/{playlist_id}/videos/{upload_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_video_from_playlist(
    playlist_id: int,
    upload_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove a video from a playlist."""
    # Validate upload_id format
    if not upload_id or len(upload_id) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    try:
        # Check playlist ownership
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Check video ownership
        video = crud.get_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Remove video from playlist
        result = crud.remove_video_from_playlist(db, playlist_id, video.id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not in playlist",
            )

        logger.info(
            f"User '{current_user.username}' removed video {upload_id} from playlist {playlist_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to remove video {upload_id} from playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove video from playlist",
        )


@router.get("/{playlist_id}/videos", response_model=schemas.APIResponse)
def get_playlist_videos(
    request: Request,
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get videos in a playlist."""
    try:
        # Check playlist ownership
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        playlist_videos = crud.get_playlist_videos(db, playlist_id)
        videos = []
        for pv in playlist_videos:
            video = crud.get_video(db, pv.video_id)
            if video:
                videos.append(
                    {
                        "upload_id": video.upload_id,
                        "title": video.title,
                        "position": pv.position,
                    }
                )

        logger.info(
            f"User '{current_user.username}' listed videos in playlist {playlist_id}: {len(videos)} videos"
        )
        return schemas.APIResponse(
            data=videos,
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message=f"Retrieved {len(videos)} videos from playlist",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get videos for playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve playlist videos",
        )


@router.put("/{playlist_id}/videos/{upload_id}", response_model=schemas.APIResponse)
def update_video_position(
    request: Request,
    playlist_id: int,
    upload_id: str,
    video_data: schemas.PlaylistVideoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update video position in playlist."""
    # Validate upload_id format
    if not upload_id or len(upload_id) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    try:
        # Check playlist ownership
        playlist = crud.get_playlist(db, playlist_id)
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )
        if playlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Check video ownership
        video = crud.get_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Update position
        result = crud.update_video_position_in_playlist(
            db, playlist_id, video.id, video_data.position
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video not in playlist",
            )

        logger.info(
            f"User '{current_user.username}' updated position of video {upload_id} in playlist {playlist_id} to {video_data.position}"
        )
        return schemas.APIResponse(
            data={
                "playlist_id": playlist_id,
                "video_upload_id": upload_id,
                "position": video_data.position,
            },
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Video position updated successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update video position for {upload_id} in playlist {playlist_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update video position",
        )
