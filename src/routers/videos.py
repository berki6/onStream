from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import subprocess
import shutil
from src.schema import schemas
from src.services import crud
from src.core.database import get_db
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.logger import get_logger, log_timing

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


def generate_thumbnail(file_path: str, video_id: int) -> Optional[str]:
    """Generate thumbnail using FFmpeg."""
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{video_id}.jpg")
    try:
        cmd = [
            "ffmpeg",
            "-i",
            file_path,
            "-vf",
            "thumbnail,scale=320:180",
            "-frames:v",
            "1",
            thumbnail_path,
            "-y",  # Overwrite output
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return thumbnail_path
    except subprocess.CalledProcessError:
        return None


@log_timing
def transcode_video(video_id: int, video_path: str, hls_path: str):
    """Background task to transcode video to HLS using FFmpeg, update status, and generate thumbnail."""
    from src.core.database import SessionLocal
    from src.services.crud import update_video_status

    logger.info(f"Starting transcoding for video ID {video_id}")
    db = SessionLocal()
    try:
        # Generate thumbnail first
        thumbnail_path = generate_thumbnail(video_path, video_id)

        # Transcode to HLS
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-start_number",
            "0",
            "-hls_time",
            "10",
            "-hls_list_size",
            "0",
            "-f",
            "hls",
            hls_path,
            "-y",
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Update DB on success
        video = crud.update_video_status(db, video_id, "ready")
        if video:
            if thumbnail_path:
                video.thumbnail_path = thumbnail_path
            db.commit()
            db.refresh(video)
        logger.info(f"Transcoding completed successfully for video ID {video_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Transcoding failed for video ID {video_id}: {e}")
        crud.update_video_status(db, video_id, "error")
    finally:
        db.close()


@router.post(
    "/", response_model=schemas.VideoResponse, status_code=status.HTTP_201_CREATED
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logger.info(
        f"User '{current_user.username}' starting video upload: {file.filename}"
    )
    # Validate size (500MB)
    if file.size is None or file.size > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Max 500MB.")

    if file.content_type is None or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    # Validate with ffprobe (quick check)
    temp_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Probe to validate and get duration
        duration = probe_video_duration(temp_path)
        if duration is None:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail="Invalid or corrupt video file")

        # Rename to video_id (create entry first)
        video = crud.create_video(
            db, schemas.VideoCreate(title=title, duration=duration), current_user.id
        )
        file_path = os.path.join(UPLOAD_DIR, f"{video.id}_{file.filename}")
        os.rename(temp_path, file_path)
        video.file_path = file_path
        db.commit()
        db.refresh(video)

        # Queue transcode
        hls_path = os.path.join(HLS_DIR, f"{video.id}.m3u8")
        background_tasks.add_task(transcode_video, video.id, file_path, hls_path)

        logger.info(
            f"Video upload successful for user '{current_user.username}': video ID {video.id}"
        )
        return video
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


@router.get("/{video_id}", response_model=schemas.VideoResponse)
def get_video(
    video_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    video = crud.get_video(db, video_id)
    if not video or video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    logger.info(f"User '{current_user.username}' accessed video ID {video_id}")
    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    video = crud.delete_video(db, video_id)
    if not video or video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    # Clean up files
    if video.file_path and os.path.exists(video.file_path):
        os.remove(video.file_path)
    if video.hls_path and os.path.exists(video.hls_path):
        # Remove HLS files (playlist and segments)
        for f in os.listdir(HLS_DIR):
            if f.startswith(f"{video_id}."):
                os.remove(os.path.join(HLS_DIR, f))
    logger.info(f"User '{current_user.username}' deleted video ID {video_id}")
