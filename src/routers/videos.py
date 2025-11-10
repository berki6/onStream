import os
import shutil
import subprocess
from typing import List, Optional

import redis
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status,
)
from sqlalchemy.orm import Session

from src.core.auth import get_current_user
from src.core.config import settings
from src.core.database import get_db
from src.core.logger import get_logger
from src.schema import schemas
from src.services import crud

router = APIRouter()

logger = get_logger(__name__)

UPLOAD_DIR = settings.VIDEO_UPLOAD_DIR
HLS_DIR = settings.VIDEO_HLS_DIR
THUMBNAIL_DIR = settings.VIDEO_THUMBNAIL_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HLS_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)


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
    title: Optional[str] = None,
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

    # Validate size (500MB)
    if file.size is None or file.size > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Max 500MB.")

    if file.content_type is None or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    # Validate with ffprobe (quick check)
    import uuid

    temp_filename = f"temp_{uuid.uuid4().hex}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)  # type: ignore[arg-type]

        # Probe to validate and get duration
        duration = probe_video_duration(temp_path)
        if duration is None:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail="Invalid or corrupt video file")

        # Create video entry with temporary file_path (will be updated after getting ID)
        temp_video = crud.create_video(
            db,
            schemas.VideoCreate(title=title, duration=duration, file_path="temp"),
            current_user.id,
        )

        # Create video job for tracking processing status
        crud.create_video_job(
            db, schemas.VideoJobCreate(upload_id=temp_video.upload_id)
        )

        # Now create the actual file_path with the video ID
        final_filename = f"{temp_video.id}_{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, final_filename)
        os.rename(temp_path, file_path)

        # Update the video with the correct file_path
        temp_video.file_path = file_path
        db.commit()
        db.refresh(temp_video)

        # Push job to Redis queue for processing
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.lpush("video_jobs_queue", temp_video.upload_id)

        logger.info(
            f"Video upload successful for user '{current_user.username}': video ID {temp_video.id}, queued for processing"
        )
        return temp_video
    except Exception as e:
        logger.error(
            f"Video upload failed for user '{current_user.username}': {str(e)}"
        )
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


@router.get("/", response_model=List[schemas.VideoResponse])
def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    videos = crud.get_videos_by_user(db, current_user.id, skip=skip, limit=limit)
    logger.info(f"User '{current_user.username}' listed videos: {len(videos)} videos")
    return videos


@router.get("/{upload_id}", response_model=schemas.VideoResponse)
def get_video(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    video = crud.get_video_by_upload_id(db, upload_id)
    if not video or video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    logger.info(f"User '{current_user.username}' accessed video upload_id {upload_id}")
    return video


@router.get("/{upload_id}/job", response_model=schemas.VideoJobResponse)
def get_video_job(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    video = crud.get_video_by_upload_id(db, upload_id)
    if not video or video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")

    job = crud.get_job_for_video(db, video)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(
        f"User '{current_user.username}' checked job status for video upload_id {upload_id}"
    )
    return job


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    video = crud.delete_video_by_upload_id(db, upload_id)
    if not video or video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    # Clean up files
    if video.file_path and os.path.exists(video.file_path):
        os.remove(video.file_path)
    if video.hls_path and os.path.exists(video.hls_path):
        # Remove HLS files (playlist and segments)
        for f in os.listdir(HLS_DIR):
            if f.startswith(f"{video.id}."):
                os.remove(os.path.join(HLS_DIR, f))
    logger.info(f"User '{current_user.username}' deleted video upload_id {upload_id}")
