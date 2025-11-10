from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import os
from src.services import crud
from src.core.database import get_db
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.logger import get_logger
from sqlalchemy.orm import Session
from src.schema import models

router = APIRouter()

logger = get_logger(__name__)

HLS_DIR = settings.VIDEO_HLS_DIR


@router.get("/{upload_id}/playlist.m3u8")
async def stream_hls_playlist(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Validate upload_id format (should be 8 characters, safe alphanumeric)
    if not upload_id or len(upload_id) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    # Check for valid characters (alphanumeric excluding ambiguous ones)
    import string

    safe_chars = string.ascii_letters + string.digits
    safe_chars = "".join(c for c in safe_chars if c not in "0O1Il")
    if not all(c in safe_chars for c in upload_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    try:
        video = crud.get_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        if video.status != models.VideoStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Video is not ready for streaming",
            )

        if not video.hls_path or not os.path.exists(video.hls_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stream playlist not available",
            )

        logger.info(
            f"User '{current_user.username}' accessing HLS playlist for video upload_id {upload_id}"
        )

        def iterfile():
            try:
                with open(video.hls_path, mode="rb") as file_like:
                    for chunk in iter(lambda: file_like.read(4096), b""):
                        yield chunk
            except IOError as e:
                logger.error(f"Error reading playlist file {video.hls_path}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to read stream playlist",
                )

        return StreamingResponse(iterfile(), media_type="application/vnd.apple.mpegurl")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream playlist for video {upload_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to access stream playlist",
        )


@router.get("/{upload_id}/{segment}.ts")
async def stream_hls_segment(
    upload_id: str,
    segment: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Validate upload_id format (should be 8 characters, safe alphanumeric)
    if not upload_id or len(upload_id) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    # Check for valid characters (alphanumeric excluding ambiguous ones)
    import string

    safe_chars = string.ascii_letters + string.digits
    safe_chars = "".join(c for c in safe_chars if c not in "0O1Il")
    if not all(c in safe_chars for c in upload_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload ID format"
        )

    # Validate segment name (should be safe filename)
    if not segment or ".." in segment or "/" in segment or "\\" in segment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid segment name"
        )

    try:
        video = crud.get_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        if video.status != models.VideoStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Video is not ready for streaming",
            )

        if not video.hls_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stream playlist not found",
            )

        # Segments are in the same directory as the playlist
        hls_dir = os.path.dirname(video.hls_path)
        ts_path = os.path.join(hls_dir, f"{segment}.ts")
        if not os.path.exists(ts_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stream segment not found"
            )

        logger.info(
            f"User '{current_user.username}' accessing HLS segment {segment} for video upload_id {upload_id}"
        )

        def iterfile():
            try:
                with open(ts_path, mode="rb") as file_like:
                    for chunk in iter(lambda: file_like.read(4096), b""):
                        yield chunk
            except IOError as e:
                logger.error(f"Error reading segment file {ts_path}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to read stream segment",
                )

        return StreamingResponse(iterfile(), media_type="video/MP2T")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to stream segment {segment} for video {upload_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to access stream segment",
        )
