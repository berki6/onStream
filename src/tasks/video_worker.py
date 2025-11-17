#!/usr/bin/env python3
"""
Redis-based video processing worker.

This worker consumes video processing jobs from a Redis queue and processes them
using FFmpeg to transcode videos to HLS format and generate thumbnails.
"""

import os
import subprocess
import redis
import signal
import sys
import threading
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from src.schema import models
from src.core.database import engine
from src.core.config import settings
from src.core.logger import get_logger
from src.utils.paths import to_relative_path, to_absolute_path, ensure_dir

logger = get_logger(__name__)

# Database setup
Session = sessionmaker(bind=engine)

# Redis setup
redis_client = redis.from_url(settings.REDIS_URL)

# Shutdown event for graceful termination
shutdown_event = threading.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Worker received shutdown signal")
    shutdown_event.set()


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
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        logger.warning(f"Input video file not found for thumbnail: {video_path}")
        return None

    thumbnail_path = settings.VIDEO_THUMBNAIL_DIR / f"{video_id}.jpg"
    try:
        # Ensure thumbnail directory exists
        ensure_dir(thumbnail_path)

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
            str(thumbnail_path),
            "-y",  # Overwrite output
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return to_relative_path(thumbnail_path)
    except (subprocess.CalledProcessError, Exception) as e:
        if isinstance(e, subprocess.CalledProcessError):
            short_error = extract_concise_error(e.stderr)
        else:
            short_error = str(e)
        logger.error(f"Thumbnail generation failed for video {video_id}: {short_error}")
        return None


def process_video(session, job):
    """Process a video job: transcode to HLS and generate thumbnail."""
    # Check if shutdown was requested before starting
    if shutdown_event.is_set():
        logger.info("Shutdown requested, skipping video processing")
        return

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

    upload_file = to_absolute_path(video.file_path)
    if not upload_file.exists():
        logger.error(f"Input video file not found: {upload_file}")
        update_job_progress(
            session, job, 0, status="error", message="Input video file not found"
        )
        video.status = models.VideoStatus.ERROR
        session.commit()
        return

    output_dir = settings.VIDEO_HLS_DIR / job.upload_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Update video status to PROCESSING
    video.status = models.VideoStatus.PROCESSING
    session.commit()
    logger.info(f"Video processing started for upload_id {job.upload_id}")

    try:
        update_job_progress(session, job, 10, message="Starting transcoding")

        # Generate thumbnail first
        if shutdown_event.is_set():
            logger.info("Shutdown requested, skipping thumbnail generation")
            return
        thumbnail_path = generate_thumbnail(str(upload_file), video.id)
        if thumbnail_path:
            update_job_progress(session, job, 30, message="Thumbnail generated")
        else:
            update_job_progress(
                session, job, 30, message="Thumbnail generation skipped"
            )

        # Transcode to HLS
        if shutdown_event.is_set():
            logger.info("Shutdown requested, skipping HLS transcoding")
            return
        update_job_progress(session, job, 50, message="Transcoding to HLS...")
        hls_cmd = [
            "ffmpeg",
            "-i",
            str(upload_file),
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
            str(output_dir / "segment_%03d.ts"),
            "-f",
            "hls",
            str(output_dir / "index.m3u8"),
            "-y",
        ]
        result = subprocess.run(hls_cmd, check=True, capture_output=True, text=True)

        # Update video status and job completion
        video.status = models.VideoStatus.READY
        video.hls_path = to_relative_path(output_dir / "index.m3u8")
        if thumbnail_path:
            video.thumbnail_path = thumbnail_path
        session.commit()

        update_job_progress(
            session, job, 100, status="ready", message="Job completed successfully"
        )
        logger.info(f"Video processing completed for upload_id {job.upload_id}")

    except (subprocess.CalledProcessError, Exception) as e:
        if isinstance(e, subprocess.CalledProcessError):
            short_error = extract_concise_error(e.stderr)
        else:
            short_error = str(e)
        logger.error(
            f"Video processing failed for upload_id {job.upload_id}: {short_error}"
        )
        update_job_progress(
            session, job, 0, status="error", message=f"Processing failed: {short_error}"
        )

        # Update video status to error
        video.status = models.VideoStatus.ERROR
        session.commit()


def process_job(upload_id: str):
    """Process a single job from the queue."""
    logger.info(f"Processing job for upload_id: {upload_id}")

    session = Session()
    try:
        # Get job from database
        job = session.query(models.VideoJob).filter_by(upload_id=upload_id).first()
        if job:
            process_video(session, job)
        else:
            logger.error(f"Job not found for upload_id: {upload_id}")
    finally:
        session.close()


def run_worker():
    """Main worker loop that consumes jobs from Redis queue."""
    # Set up signal handlers only in development environment
    is_development = settings.ENV == "development"
    if is_development:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers enabled for development environment")
    else:
        # In production, completely ignore keyboard interrupts
        # Process lifecycle is managed by supervisor/systemd
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C
        logger.info(
            "Signal handlers disabled for production environment (using supervisor)"
        )

    logger.info("Video processing worker started")

    while not shutdown_event.is_set():
        try:
            # BLPOP blocks until an element is available or timeout
            result = redis_client.blpop("video_jobs_queue", timeout=1.0)
            if result is None:
                # Queue is empty, continue waiting
                continue
            _, upload_id_bytes = result
            upload_id = upload_id_bytes.decode("utf-8")

            process_job(upload_id)

        except KeyboardInterrupt:
            if is_development:
                logger.info("Worker received shutdown signal")
                break
            # In production, KeyboardInterrupt is ignored (signal.SIG_IGN)
            # This should never be reached due to signal.SIG_IGN, but just in case
            continue
        except Exception as e:
            logger.error(f"Worker error: {e}")
            # Continue processing other jobs even if one fails

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    run_worker()
