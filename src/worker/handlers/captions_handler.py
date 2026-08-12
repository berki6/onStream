"""Captions / transcription job handler."""

from __future__ import annotations

import json

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import engine
from src.infrastructure.media.captions import extract_audio, segments_to_vtt, transcribe
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.webhooks.delivery import emit_video_event
from src.utils.paths import to_relative_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)


def process_captions(upload_id: str) -> None:
    session = Session()
    try:
        video = (
            session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if not video:
            logger.error(f"Captions: video not found for {upload_id}")
            job_queue.mark_job_failed(
                upload_id,
                "Video not found",
                job_type="captions",
                error_code=ErrorCode.VIDEO_NOT_FOUND,
            )
            return

        from src.infrastructure.storage import get_storage

        storage = get_storage()
        try:
            local_path = storage.ensure_local(video.file_path)
        except Exception as e:
            job_queue.mark_job_failed(
                upload_id,
                str(e),
                job_type="captions",
                error_code=ErrorCode.INTERNAL_STORAGE_FAILURE,
            )
            return

        hls_dir = settings.VIDEO_HLS_DIR / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        audio_path = hls_dir / "audio.wav"
        try:
            extract_audio(str(local_path), str(audio_path))
            source = str(audio_path)
        except Exception:
            source = str(local_path)

        result = transcribe(source, provider=settings.AI_CAPTIONS_PROVIDER)
        segments = result.get("segments") or []
        language = result.get("language") or "en"
        if not segments:
            # Last resort so playback always gets a valid WebVTT file.
            from src.infrastructure.media.captions import _mock_segments
            from src.infrastructure.media.ffmpeg import probe_duration

            duration = probe_duration(source) or 30.0
            segments = _mock_segments(duration)
            logger.warning(
                "Captions empty after normalize for %s; wrote mock VTT", upload_id
            )

        vtt_path = hls_dir / "captions.vtt"
        vtt_path.write_text(segments_to_vtt(segments), encoding="utf-8")

        transcript_path = hls_dir / "transcript.json"
        transcript_path.write_text(
            json.dumps({"language": language, "segments": segments}, indent=2),
            encoding="utf-8",
        )

        video.caption_vtt_path = to_relative_path(vtt_path)
        video.transcript_path = to_relative_path(transcript_path)
        video.detected_language = language
        session.commit()

        # Persist SUBTITLES into on-disk master (playback also injects at serve time).
        master_path = hls_dir / "master.m3u8"
        if master_path.is_file():
            try:
                from src.infrastructure.media.abr import inject_subtitle_track

                raw = master_path.read_text(encoding="utf-8")
                injected = inject_subtitle_track(raw, captions_uri="captions.vtt")
                if injected != raw:
                    master_path.write_text(injected, encoding="utf-8")
                    try:
                        storage.put_file(
                            to_relative_path(master_path), master_path
                        )
                    except Exception:
                        # Local backend may no-op / use same path; ignore sync miss.
                        pass
                    logger.info(
                        "Injected SUBTITLES into on-disk master for %s", upload_id
                    )
            except Exception as exc:
                logger.warning(
                    "Could not persist captions into master for %s: %s",
                    upload_id,
                    exc,
                )

        emit_video_event(
            session,
            video,
            "video.captions_ready",
            {"language": language, "segment_count": len(segments)},
        )
        job_queue.mark_job_completed(upload_id, job_type="captions")

        # Downstream jobs that need captions
        if settings.AI_ENABLED and settings.AI_CHAPTERS_ENABLED:
            job_queue.enqueue_job(upload_id, session, job_type="chapters")
        if settings.AI_ENABLED and settings.AI_EMBEDDINGS_ENABLED:
            job_queue.enqueue_job(upload_id, session, job_type="embeddings")

        logger.info(f"Captions ready for {upload_id} ({len(segments)} segments)")
    except Exception as e:
        logger.error(f"Captions failed for {upload_id}: {e}")
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type="captions",
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
