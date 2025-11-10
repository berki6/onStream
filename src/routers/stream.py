from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import os
from src.services import crud
from src.core.database import get_db
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.logger import get_logger
from sqlalchemy.orm import Session

router = APIRouter()

logger = get_logger(__name__)

HLS_DIR = settings.VIDEO_HLS_DIR


@router.get("/{video_id}/playlist.m3u8")
async def stream_hls_playlist(
    video_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    video = crud.get_video(db, video_id)
    if not video or video.user_id != current_user.id or video.status != "ready":
        raise HTTPException(status_code=404, detail="Video not ready or not found")

    hls_path = os.path.join(HLS_DIR, f"{video_id}.m3u8")
    if not os.path.exists(hls_path):
        raise HTTPException(status_code=404, detail="HLS playlist not found")

    logger.info(
        f"User '{current_user.username}' accessing HLS playlist for video ID {video_id}"
    )

    def iterfile():
        with open(hls_path, mode="rb") as file_like:
            for chunk in iter(lambda: file_like.read(4096), b""):
                yield chunk

    return StreamingResponse(iterfile(), media_type="application/vnd.apple.mpegurl")


@router.get("/{video_id}/{segment}.ts")
async def stream_hls_segment(
    video_id: int,
    segment: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    video = crud.get_video(db, video_id)
    if not video or video.user_id != current_user.id or video.status != "ready":
        raise HTTPException(status_code=404, detail="Video not ready or not found")

    ts_path = os.path.join(HLS_DIR, f"{video_id}.{segment}.ts")
    if not os.path.exists(ts_path):
        raise HTTPException(status_code=404, detail="Segment not found")

    logger.info(
        f"User '{current_user.username}' accessing HLS segment {segment} for video ID {video_id}"
    )

    def iterfile():
        with open(ts_path, mode="rb") as file_like:
            for chunk in iter(lambda: file_like.read(4096), b""):
                yield chunk

    return StreamingResponse(iterfile(), media_type="video/MP2T")
