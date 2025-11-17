#!/usr/bin/env python3
"""
Redis-based video processing worker.

This worker consumes video processing jobs from a Redis queue and processes them
using FFmpeg to transcode videos to HLS format and generate thumbnails.
"""

import subprocess
import signal
import threading
import time
import re
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from src.schema import models
from src.core.database import engine
from src.core.config import settings
from src.core.logger import get_logger
from src.utils.paths import to_relative_path, to_absolute_path, ensure_dir
from src.services.job_queue import job_queue

logger = get_logger(__name__)

# Database setup
Session = sessionmaker(bind=engine)

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


def calculate_eta(file_size_bytes: int, progress_percent: float) -> int:
    """
    Calculate estimated time remaining based on file size and current progress.

    This is a simple heuristic that assumes:
    - Processing time roughly correlates with file size
    - Average processing rate is ~50MB/minute (adjust based on your hardware)
    - Returns ETA in seconds
    """
    if progress_percent >= 100 or progress_percent <= 0:
        return 0

    # Base processing rate: assume 50MB takes ~60 seconds (adjust for your hardware)
    base_rate_mb_per_minute = 50  # MB per minute
    base_time_per_mb = 60 / base_rate_mb_per_minute  # seconds per MB

    # Calculate file size in MB
    file_size_mb = file_size_bytes / (1024 * 1024)

    # Estimate total processing time for this file
    estimated_total_seconds = file_size_mb * base_time_per_mb

    # Calculate remaining time based on current progress
    progress_fraction = progress_percent / 100.0
    remaining_fraction = 1.0 - progress_fraction
    eta_seconds = int(estimated_total_seconds * remaining_fraction)

    return max(0, eta_seconds)  # Ensure non-negative


def monitor_ffmpeg_progress(process, session, job, file_size, start_time):
    """Monitor FFmpeg progress and update job status in real-time."""
    progress_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.\d+")

    while process.poll() is None:  # While FFmpeg is still running
        if shutdown_event.is_set():
            break

        line = process.stderr.readline()
        if not line:
            continue

        line = line.decode("utf-8", errors="ignore").strip()

        # Look for time progress in FFmpeg output
        match = progress_pattern.search(line)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            total_seconds_processed = hours * 3600 + minutes * 60 + seconds

            # Estimate total duration (rough heuristic: assume 30fps average)
            # This is approximate - FFmpeg doesn't give us total duration upfront
            estimated_total_duration = max(
                60, total_seconds_processed * 2
            )  # Conservative estimate

            # Calculate progress percentage
            progress_percent = min(
                95, (total_seconds_processed / estimated_total_duration) * 100
            )

            # Update progress and ETA
            eta = calculate_eta(file_size, progress_percent)
            update_job_progress(
                session,
                job,
                int(progress_percent),
                eta=eta,
                message=f"Transcoding... ({total_seconds_processed}s processed)",
            )

        time.sleep(0.1)  # Small delay to avoid overwhelming the database

    # Final update when transcoding completes
    if process.returncode == 0:
        update_job_progress(
            session,
            job,
            95,
            eta=calculate_eta(file_size, 95),
            message="Finalizing HLS segments...",
        )
    else:
        update_job_progress(
            session, job, 0, status="error", message="Transcoding failed"
        )


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

    # Get file size for ETA calculation
    file_size = upload_file.stat().st_size

    output_dir = settings.VIDEO_HLS_DIR / job.upload_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Update video status to PROCESSING
    video.status = models.VideoStatus.PROCESSING
    session.commit()
    logger.info(f"Video processing started for upload_id {job.upload_id}")

    try:
        # Start transcoding (10%)
        eta = calculate_eta(file_size, 10)
        update_job_progress(session, job, 10, eta=eta, message="Starting transcoding")

        # Generate thumbnail first
        if shutdown_event.is_set():
            logger.info("Shutdown requested, skipping thumbnail generation")
            return
        thumbnail_path = generate_thumbnail(str(upload_file), video.id)
        if thumbnail_path:
            eta = calculate_eta(file_size, 30)
            update_job_progress(
                session, job, 30, eta=eta, message="Thumbnail generated"
            )
        else:
            eta = calculate_eta(file_size, 30)
            update_job_progress(
                session, job, 30, eta=eta, message="Thumbnail generation skipped"
            )

        # Transcode to HLS with real-time progress monitoring
        if shutdown_event.is_set():
            logger.info("Shutdown requested, skipping HLS transcoding")
            return
        eta = calculate_eta(file_size, 50)
        update_job_progress(session, job, 50, eta=eta, message="Transcoding to HLS...")

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
            "-progress",
            "pipe:2",  # Send progress to stderr
        ]

        # Start FFmpeg process
        process = subprocess.Popen(
            hls_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # We'll decode manually
        )

        # Start progress monitoring in a separate thread
        start_time = time.time()
        progress_thread = threading.Thread(
            target=monitor_ffmpeg_progress,
            args=(process, session, job, file_size, start_time),
        )
        progress_thread.start()

        # Wait for FFmpeg to complete
        process.wait()
        progress_thread.join()

        # Check if FFmpeg succeeded
        if process.returncode != 0:
            stderr_output = ""
            if process.stderr:
                try:
                    stderr_output = process.stderr.read().decode(
                        "utf-8", errors="ignore"
                    )
                except:
                    stderr_output = "Unable to read stderr"
            short_error = extract_concise_error(stderr_output)
            raise subprocess.CalledProcessError(
                process.returncode, hls_cmd, stderr=stderr_output
            )

        # Update video status and job completion
        video.status = models.VideoStatus.READY
        video.hls_path = to_relative_path(output_dir / "index.m3u8")
        if thumbnail_path:
            video.thumbnail_path = thumbnail_path
        session.commit()

        update_job_progress(
            session,
            job,
            100,
            eta=0,
            status="ready",
            message="Job completed successfully",
        )
        logger.info(f"Video processing completed for upload_id {job.upload_id}")

        # Mark job as completed in database queue
        job_queue.mark_job_completed(job.upload_id)

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

        # Mark job as failed in database queue
        job_queue.mark_job_failed(job.upload_id, short_error)


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
            # Try to recover jobs to Redis if it's available
            job_queue.recover_jobs_to_redis()

            # Dequeue job (from Redis or database fallback)
            upload_id = job_queue.dequeue_job(timeout=1)
            if upload_id is None:
                # Queue is empty, continue waiting
                continue

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
