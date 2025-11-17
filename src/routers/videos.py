import os
import shutil
import subprocess
from typing import List, Optional
from pathlib import Path
import uuid

import redis
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
)
from sqlalchemy.orm import Session

from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_db
from src.core.logger import get_logger
from src.schema import schemas
from src.services import crud
from src.utils.paths import to_relative_path, to_absolute_path, ensure_dir

router = APIRouter()

logger = get_logger(__name__)


def probe_video_duration(file_path: str) -> Optional[float]:
    """Use ffprobe to get video duration in seconds."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.CalledProcessError, ValueError):
        return None


@router.post(
    "/", response_model=schemas.VideoResponse, status_code=status.HTTP_201_CREATED
)
async def upload_video(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logger.info(
        f"User '{current_user.username}' starting video upload: {file.filename}"
    )

    # Auto-generate title from filename if not provided
    if not title and file.filename:
        # Remove file extension and clean up filename
        filename_without_ext = os.path.splitext(file.filename)[0]
        # Replace underscores and hyphens with spaces, capitalize words
        title = filename_without_ext.replace("_", " ").replace("-", " ").title()

    # Ensure we have a title
    if not title:
        title = "Untitled Video"

    # Validate size
    if file.size is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size cannot be determined",
        )
    if file.size > settings.MAX_UPLOAD_SIZE:
        max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size_mb}MB",
        )

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only video files are allowed",
        )

    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
        )

    # Validate title length if provided
    if title and len(title.strip()) > settings.MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Title must be {settings.MAX_TITLE_LENGTH} characters or less",
        )

    # Validate with ffprobe (quick check)
    import uuid

    temp_filename = f"temp_{uuid.uuid4().hex}_{file.filename}"
    temp_path = settings.VIDEO_UPLOAD_DIR / temp_filename
    ensure_dir(temp_path)
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)  # type: ignore[arg-type]

        # Probe to validate and get duration
        duration = probe_video_duration(str(temp_path))
        if duration is None:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupt video file",
            )

        if duration < 1:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video is too short (minimum 1 second)",
            )

        if duration > settings.MAX_VIDEO_DURATION_SECONDS:
            max_duration_minutes = settings.MAX_VIDEO_DURATION_SECONDS // 60
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video is too long (maximum {max_duration_minutes} minutes)",
            )

        # Create video entry with temporary file_path
        try:
            temp_video = crud.create_video(
                db,
                schemas.VideoCreate(
                    title=title,
                    description=description,
                    duration=duration,
                    file_path="temp",
                ),
                current_user.id,
            )
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to create video record: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create video record",
            )

        # Create video job for tracking processing status
        try:
            crud.create_video_job(
                db, schemas.VideoJobCreate(upload_id=temp_video.upload_id)
            )
        except Exception as e:
            db.rollback()
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to create video job: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create processing job",
            )

        # Now create the actual file_path with the video ID
        final_filename = f"{temp_video.id}_{uuid.uuid4().hex}_{file.filename}"
        file_path = settings.VIDEO_UPLOAD_DIR / final_filename

        try:
            temp_path.rename(file_path)
        except OSError as e:
            db.rollback()
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to move video file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save video file",
            )

        # Update the video with the correct file_path
        try:
            temp_video.file_path = to_relative_path(file_path)
            db.commit()
            db.refresh(temp_video)
        except Exception as e:
            db.rollback()
            file_path.unlink(missing_ok=True)
            logger.error(f"Failed to update video record: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update video record",
            )

        # Push job to Redis queue for processing
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.lpush("video_jobs_queue", temp_video.upload_id)
        except Exception as e:
            logger.warning(f"Failed to queue video for processing: {str(e)}")
            # Don't fail the upload, just log the warning

        logger.info(
            f"Video upload successful for user '{current_user.username}': video ID {temp_video.id}, queued for processing"
        )
        return temp_video
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Video upload failed for user '{current_user.username}': {str(e)}"
        )
        # Clean up any temporary files
        for path in [temp_path, file_path if "file_path" in locals() else None]:
            if path and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video upload failed",
        )


@router.get("/", response_model=List[schemas.VideoResponse])
def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
        videos = crud.get_videos_by_user(db, current_user.id, skip=skip, limit=limit)
        logger.info(
            f"User '{current_user.username}' listed videos: {len(videos)} videos"
        )
        return videos
    except Exception as e:
        logger.error(
            f"Failed to list videos for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve videos",
        )


@router.get("/{upload_id}", response_model=schemas.VideoResponse)
def get_video(
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

        logger.info(
            f"User '{current_user.username}' accessed video upload_id {upload_id}"
        )
        return video
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get video {upload_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video",
        )


@router.get("/{upload_id}/job", response_model=schemas.VideoJobResponse)
def get_video_job(
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

        job = crud.get_job_for_video(db, video)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        logger.info(
            f"User '{current_user.username}' checked job status for video upload_id {upload_id}"
        )
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get job for video {upload_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job status",
        )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
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
        video = crud.delete_video_by_upload_id(db, upload_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )
        if video.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Clean up files with error handling
        try:
            if video.file_path:
                file_path = to_absolute_path(video.file_path)
                if file_path.exists():
                    file_path.unlink()
        except OSError as e:
            logger.warning(f"Failed to remove video file {video.file_path}: {str(e)}")

        try:
            if video.hls_path:
                hls_path = to_absolute_path(video.hls_path)
                hls_dir = hls_path.parent
                if hls_dir.exists():
                    shutil.rmtree(hls_dir)  # Remove entire HLS directory
        except OSError as e:
            logger.warning(
                f"Failed to clean up HLS directory for video {video.id}: {str(e)}"
            )

        try:
            if video.thumbnail_path:
                thumb_path = to_absolute_path(video.thumbnail_path)
                if thumb_path.exists():
                    thumb_path.unlink()
        except OSError as e:
            logger.warning(
                f"Failed to remove thumbnail {video.thumbnail_path}: {str(e)}"
            )

        logger.info(
            f"User '{current_user.username}' deleted video upload_id {upload_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete video {upload_id} for user '{current_user.username}': {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video",
        )
