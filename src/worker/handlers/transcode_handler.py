"""Video transcode job handler (ABR HLS ladder + storyboard)."""

from __future__ import annotations

import subprocess
import threading
from typing import Dict, List

from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db.session import engine
from src.infrastructure.media.abr import select_ladder, write_master_playlist
from src.infrastructure.media.ffmpeg import (
    encode_rendition,
    extract_concise_error,
    probe_height,
)
from src.infrastructure.media.storyboard import generate_storyboard
from src.infrastructure.media.thumbnail import generate_thumbnail
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.webhooks.delivery import emit_video_event
from src.infrastructure.db import models
from src.utils.paths import to_absolute_path, to_relative_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)
shutdown_event = threading.Event()


def update_job_progress(
    session,
    job,
    progress,
    eta=0,
    message=None,
    status=None,
    stage=None,
):
    job.progress = progress
    job.eta = eta
    if message:
        job.message = message
    if status:
        job.status = status
    if stage:
        job.stage = stage
        job.status = stage
    session.commit()


def calculate_eta(file_size_bytes: int, progress_percent: float) -> int:
    if progress_percent >= 100 or progress_percent <= 0:
        return 0
    base_rate_mb_per_minute = 50
    file_size_mb = file_size_bytes / (1024 * 1024)
    total_estimated_seconds = (file_size_mb / base_rate_mb_per_minute) * 60
    remaining_percent = 100 - progress_percent
    return max(1, int(total_estimated_seconds * (remaining_percent / 100)))


def process_video(session, job):
    if shutdown_event.is_set():
        return

    video = (
        session.query(models.Video)
        .filter(models.Video.upload_id == job.upload_id)
        .first()
    )
    if not video:
        update_job_progress(
            session, job, 0, status="error", stage="error", message="Video not found"
        )
        return

    if job.cancel_requested:
        update_job_progress(
            session,
            job,
            0,
            status="cancelled",
            stage=models.JobStage.CANCELLED.value,
            message="Cancelled",
        )
        return

    from src.infrastructure.storage import get_storage

    storage = get_storage()
    try:
        upload_file = storage.ensure_local(video.file_path)
    except Exception as e:
        update_job_progress(
            session,
            job,
            0,
            status="error",
            stage="error",
            message=f"Input missing: {e}",
        )
        video.status = models.VideoStatus.ERROR
        session.commit()
        emit_video_event(session, video, "video.failed", {"error": str(e)})
        return

    file_size = upload_file.stat().st_size
    output_dir = settings.VIDEO_HLS_DIR / job.upload_id
    output_dir.mkdir(parents=True, exist_ok=True)

    video.status = models.VideoStatus.PROCESSING
    session.commit()

    try:
        update_job_progress(
            session,
            job,
            5,
            eta=calculate_eta(file_size, 5),
            stage=models.JobStage.ANALYZING.value,
            message="Analyzing source",
        )
        source_height = probe_height(str(upload_file))
        ladder = select_ladder(source_height)

        if job.cancel_requested or shutdown_event.is_set():
            update_job_progress(
                session,
                job,
                0,
                status="cancelled",
                stage=models.JobStage.CANCELLED.value,
                message="Cancelled",
            )
            return

        update_job_progress(
            session,
            job,
            15,
            eta=calculate_eta(file_size, 15),
            stage=models.JobStage.TRANSCODING.value,
            message="Generating thumbnail",
        )
        thumbnail_path = generate_thumbnail(str(upload_file), video.id)

        storyboard_path, storyboard_vtt = generate_storyboard(
            str(upload_file), output_dir, video.duration or 0
        )

        encoded: List[Dict] = []
        n = len(ladder)
        for i, rung in enumerate(ladder):
            if job.cancel_requested or shutdown_event.is_set():
                update_job_progress(
                    session,
                    job,
                    0,
                    status="cancelled",
                    stage=models.JobStage.CANCELLED.value,
                    message="Cancelled",
                )
                return
            progress = 20 + int(60 * (i / max(n, 1)))
            update_job_progress(
                session,
                job,
                progress,
                eta=calculate_eta(file_size, progress),
                stage=models.JobStage.TRANSCODING.value,
                message=f"Transcoding {rung['height']}p ({i+1}/{n})",
            )
            rendition_dir = output_dir / f"{rung['height']}p"
            encode_rendition(
                upload_file,
                rendition_dir,
                rung["height"],
                rung["bitrate_k"],
                settings.HLS_SEGMENT_SECONDS,
            )
            encoded.append(rung)

        # Optional quality gate against highest rung vs source
        if settings.QUALITY_GATE_ENABLED and encoded:
            from src.infrastructure.media.quality import evaluate_quality_gate

            top = max(encoded, key=lambda r: r["height"])
            sample_seg = output_dir / f"{top['height']}p" / "segment_000.ts"
            ref_for_gate = upload_file
            if sample_seg.is_file():
                score, passed = evaluate_quality_gate(ref_for_gate, sample_seg)
                if score is not None:
                    video.quality_score = score
                if not passed:
                    emit_video_event(
                        session,
                        video,
                        "video.quality",
                        {
                            "quality_score": score,
                            "min_vmaf": settings.QUALITY_GATE_MIN_VMAF,
                            "passed": False,
                        },
                    )
                    if settings.QUALITY_GATE_STRICT:
                        raise RuntimeError(
                            f"Quality gate failed (score={score})"
                        )

        update_job_progress(
            session,
            job,
            90,
            eta=calculate_eta(file_size, 90),
            stage=models.JobStage.PACKAGING.value,
            message="Writing master playlist",
        )
        master = write_master_playlist(output_dir, encoded)

        video.status = models.VideoStatus.READY
        video.hls_path = to_relative_path(master)
        if thumbnail_path:
            video.thumbnail_path = thumbnail_path
        if storyboard_path:
            video.storyboard_path = storyboard_path
        if storyboard_vtt:
            video.storyboard_vtt_path = storyboard_vtt

        try:
            hls_prefix = to_relative_path(output_dir)
            storage.put_directory(output_dir, hls_prefix)
            if thumbnail_path:
                storage.put_file(thumbnail_path, to_absolute_path(thumbnail_path))
        except Exception as storage_err:
            logger.warning(f"Storage sync warning for {job.upload_id}: {storage_err}")

        session.commit()
        update_job_progress(
            session,
            job,
            100,
            eta=0,
            status="ready",
            stage=models.JobStage.READY.value,
            message="Job completed successfully",
        )
        job_queue.mark_job_completed(job.upload_id, job_type="transcode")
        emit_video_event(session, video, "video.ready")
        _enqueue_ai_jobs(session, job.upload_id)
        logger.info(f"ABR processing completed for {job.upload_id} ({len(encoded)} rungs)")

    except Exception as e:
        short_error = (
            extract_concise_error(e.stderr)
            if isinstance(e, subprocess.CalledProcessError)
            else str(e)
        )
        logger.error(f"Processing failed for {job.upload_id}: {short_error}")
        update_job_progress(
            session,
            job,
            0,
            status="error",
            stage=models.JobStage.ERROR.value,
            message=f"Processing failed: {short_error}",
        )
        video.status = models.VideoStatus.ERROR
        session.commit()
        job_queue.mark_job_failed(job.upload_id, short_error, job_type="transcode")
        emit_video_event(session, video, "video.failed", {"error": short_error})


def _enqueue_ai_jobs(session, upload_id: str) -> None:
    """Enqueue post-transcode AI jobs when AI_ENABLED."""
    if not settings.AI_ENABLED:
        return
    if settings.AI_MODERATION_ENABLED:
        job_queue.enqueue_job(upload_id, session, job_type="moderation")
    if settings.AI_SMART_THUMBNAIL_ENABLED:
        job_queue.enqueue_job(upload_id, session, job_type="smart_thumbnail")
    if settings.AI_CAPTIONS_ENABLED:
        job_queue.enqueue_job(upload_id, session, job_type="captions")


def process_job(upload_id: str):
    session = Session()
    try:
        job = session.query(models.VideoJob).filter_by(upload_id=upload_id).first()
        if job:
            process_video(session, job)
        else:
            logger.error(f"Job not found for upload_id: {upload_id}")
    finally:
        session.close()
