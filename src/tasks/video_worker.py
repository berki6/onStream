#!/usr/bin/env python3
"""
Redis-based video processing worker.

This worker consumes video processing jobs from a Redis queue and processes them
using FFmpeg to transcode videos to HLS format and generate thumbnails.
"""

import os
import subprocess
import redis
from sqlalchemy.orm import sessionmaker
from src.schema import models
from src.core.database import engine
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

# Database setup
Session = sessionmaker(bind=engine)

# Redis setup
redis_client = redis.from_url(settings.REDIS_URL)

# Directory paths
UPLOAD_DIR = settings.VIDEO_UPLOAD_DIR
HLS_DIR = settings.VIDEO_HLS_DIR
THUMBNAIL_DIR = settings.VIDEO_THUMBNAIL_DIR


def update_job_progress(session, job, progress, eta=0, message=None, status=None):
    """Update job progress in database."""
    job.progress = progress
    job.eta = eta
    if message:
        job.message = message
    if status:
        job.status = status
    session.commit()


from typing import Optional


def extract_concise_error(stderr_text: str, max_lines=3, max_length=250) -> str:
    """Extract concise error message from FFmpeg stderr output."""
    if not stderr_text:
        return "Unknown error (stderr is empty)"

    lines = stderr_text.strip().splitlines()
    error_keywords = [
        "error",
        "invalid",
        "fail",
        "could not",
        "no such",
        "denied",
        "unsupported",
        "unable",
        "can't open",
        "conversion failed",
    ]

    # Look for error keywords in the last few lines
    start = max(0, len(lines) - max_lines)
    for i in range(len(lines) - 1, start - 1, -1):
        line = lines[i].strip()
        if not line:
            continue
        if any(keyword in line.lower() for keyword in error_keywords):
            if i > 0 and lines[i - 1].strip():
                return f"{lines[i-1].strip()}\n{line}"[:max_length]
            return line[:max_length]

    # Fallback: return the last non-empty line
    for line in reversed(lines):
        if line.strip():
            return line[:max_length]

    return "Unknown error (no specific issue found)"


def generate_thumbnail(video_path: str, video_id: int) -> Optional[str]:
    """Generate thumbnail using FFmpeg."""
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{video_id}.jpg")
    try:
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            f"thumbnail,scale={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            thumbnail_path,
            "-y",  # Overwrite output
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return thumbnail_path
    except subprocess.CalledProcessError as e:
        short_error = extract_concise_error(e.stderr)
        logger.error(f"Thumbnail generation failed for video {video_id}: {short_error}")
        return None


def process_video(session, job):
    """Process a video job: transcode to HLS and generate thumbnail."""
    # Get video by upload_id since VideoJob uses upload_id as primary key
    video = (
        session.query(models.Video)
        .filter(models.Video.upload_id == job.upload_id)
        .first()
    )
    if not video:
        logger.error(f"Video not found for upload_id: {job.upload_id}")
        update_job_progress(session, job, 0, status="error", message="Video not found")
        return

    upload_file = os.path.normpath(
        video.file_path
    )  # Normalize path for cross-platform compatibility
    if not os.path.exists(upload_file):
        logger.error(f"Input video file not found: {upload_file}")
        update_job_progress(
            session, job, 0, status="error", message="Input video file not found"
        )
        video.status = models.VideoStatus.ERROR
        session.commit()
        return

    output_dir = os.path.normpath(os.path.join(HLS_DIR, job.upload_id))
    os.makedirs(output_dir, exist_ok=True)

    try:
        update_job_progress(session, job, 10, message="Starting transcoding")

        # Generate thumbnail first
        thumbnail_path = generate_thumbnail(upload_file, video.id)
        if thumbnail_path:
            update_job_progress(session, job, 30, message="Thumbnail generated")
        else:
            update_job_progress(
                session, job, 30, message="Thumbnail generation skipped"
            )

        # Transcode to HLS
        update_job_progress(session, job, 50, message="Transcoding to HLS...")
        hls_cmd = [
            "ffmpeg",
            "-i",
            upload_file,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-vf",
            "scale=-2:720",
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-hls_time",
            "10",
            "-hls_list_size",
            "0",
            "-hls_segment_filename",
            os.path.join(str(output_dir), "segment_%03d.ts"),
            "-f",
            "hls",
            os.path.join(str(output_dir), "index.m3u8"),
            "-y",
        ]
        result = subprocess.run(hls_cmd, check=True, capture_output=True, text=True)

        # Update video status and job completion
        video.status = models.VideoStatus.READY
        video.hls_path = os.path.join(str(output_dir), "index.m3u8")
        if thumbnail_path:
            video.thumbnail_path = thumbnail_path
        session.commit()

        update_job_progress(
            session, job, 100, status="ready", message="Job completed successfully"
        )
        logger.info(f"Video processing completed for upload_id {job.upload_id}")

    except subprocess.CalledProcessError as e:
        short_error = extract_concise_error(e.stderr)
        logger.error(
            f"Video processing failed for upload_id {job.upload_id}: {short_error}"
        )
        update_job_progress(
            session, job, 0, status="error", message=f"Processing failed: {short_error}"
        )

        # Update video status to error
        video.status = models.VideoStatus.ERROR
        session.commit()


def run_worker():
    """Main worker loop that consumes jobs from Redis queue."""
    logger.info("Video processing worker started")

    while True:
        try:
            # BLPOP blocks until an element is available
            _, upload_id_bytes = redis_client.blpop("video_jobs_queue")
            upload_id = upload_id_bytes.decode("utf-8")

            logger.info(f"Processing job for upload_id: {upload_id}")

            session = Session()
            try:
                # Get job from database
                job = (
                    session.query(models.VideoJob)
                    .filter_by(upload_id=upload_id)
                    .first()
                )
                if job:
                    process_video(session, job)
                else:
                    logger.error(f"Job not found for upload_id: {upload_id}")
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Worker error: {e}")
            # Continue processing other jobs even if one fails


if __name__ == "__main__":
    run_worker()
