"""Direct / resumable upload session service (no FastAPI)."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from src.application.enqueue import mark_enqueue_failed_and_raise
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.storage import get_storage
from src.infrastructure.webhooks.delivery import emit_video_event
from src.application.visibility import apply_visibility
from src.schemas.upload import DirectUploadCreate
from src.schemas.video import Video
from src.utils.paths import ensure_dir, to_absolute_path
from src.utils.upload_id import generate_unique_upload_id

logger = get_logger(__name__)


def _idempotency_get(db: Session, user_id: int, key: str):
    now = datetime.now(timezone.utc)
    rec = (
        db.query(models.IdempotencyRecord)
        .filter(
            models.IdempotencyRecord.user_id == user_id,
            models.IdempotencyRecord.key == key,
        )
        .first()
    )
    if not rec:
        return None
    expires = rec.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires <= now:
        return None
    return rec


def _idempotency_store(
    db: Session, user_id: int, key: str, path: str, code: int, body: dict
):
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.IDEMPOTENCY_TTL_HOURS)
    payload = json.dumps(body, default=str)
    existing = (
        db.query(models.IdempotencyRecord)
        .filter(
            models.IdempotencyRecord.user_id == user_id,
            models.IdempotencyRecord.key == key,
        )
        .first()
    )
    if existing:
        existing.response_code = code
        existing.response_body = payload
        existing.request_path = path
        existing.expires_at = expires
    else:
        db.add(
            models.IdempotencyRecord(
                user_id=user_id,
                key=key,
                request_path=path,
                response_code=code,
                response_body=payload,
                expires_at=expires,
            )
        )
    db.commit()


def create_session(
    db: Session,
    user_id: int,
    body: DirectUploadCreate,
    idempotency_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], int, bool]:
    """
    Create an upload session.

    Returns (data, status_code, is_idempotent_replay).
    """
    if idempotency_key:
        existing = _idempotency_get(db, user_id, idempotency_key)
        if existing:
            return json.loads(existing.response_body), existing.response_code or 200, True

    upload_id = generate_unique_upload_id(db)
    session_id = str(uuid.uuid4())
    ext = ".mp4"
    storage_key = f"data/uploads/{upload_id}_{session_id}{ext}"

    video = models.Video(
        upload_id=upload_id,
        user_id=user_id,
        title=body.title or "Untitled Video",
        description=body.description,
        file_path=storage_key,
        status=models.VideoStatus.PENDING,
        is_public=False,
        visibility="private",
    )
    apply_visibility(
        video, visibility=getattr(body, "visibility", None), is_public=body.is_public
    )
    db.add(video)
    db.flush()

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.UPLOAD_SESSION_EXPIRE_MINUTES
    )
    session = models.UploadSession(
        id=session_id,
        upload_id=upload_id,
        user_id=user_id,
        video_id=video.id,
        status=models.UploadSessionStatus.PENDING.value,
        storage_key=storage_key,
        bytes_received=0,
        content_type=body.content_type or "video/mp4",
        expires_at=expires_at,
    )
    db.add(session)

    job = models.VideoJob(
        upload_id=upload_id,
        status="queued",
        stage=models.JobStage.QUEUED.value,
        progress=0,
        message="Awaiting upload",
    )
    db.add(job)
    db.commit()
    db.refresh(session)
    db.refresh(video)

    storage = get_storage()
    put_url = storage.presign_put(
        storage_key,
        expires_in=settings.UPLOAD_SESSION_EXPIRE_MINUTES * 60,
        content_type=session.content_type or "video/mp4",
    )
    if settings.STORAGE_BACKEND == "local":
        put_url = f"{settings.PUBLIC_API_BASE_URL}/v1/uploads/{session_id}"

    data = {
        "session_id": session_id,
        "upload_id": upload_id,
        "upload_url": put_url,
        "expires_at": expires_at.isoformat(),
        "storage_backend": settings.STORAGE_BACKEND,
    }
    if idempotency_key:
        _idempotency_store(db, user_id, idempotency_key, "/v1/uploads", 201, data)

    return data, 201, False


def append_content(
    db: Session,
    user_id: int,
    session_id: str,
    body: bytes,
    content_range: Optional[str] = None,
) -> None:
    session = (
        db.query(models.UploadSession)
        .filter(models.UploadSession.id == session_id)
        .first()
    )
    if not session or session.user_id != user_id:
        raise AppError("Upload session not found", code=ErrorCode.UPLOAD_SESSION_NOT_FOUND)

    expires = session.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires < datetime.now(timezone.utc):
        session.status = models.UploadSessionStatus.EXPIRED.value
        db.commit()
        raise AppError("Upload session expired", code=ErrorCode.UPLOAD_SESSION_GONE)

    if not body:
        raise AppError("Empty body", code=ErrorCode.UPLOAD_BAD_REQUEST)
    if (session.bytes_received or 0) + len(body) > settings.MAX_UPLOAD_SIZE:
        raise AppError("File too large", code=ErrorCode.UPLOAD_TOO_LARGE)

    storage = get_storage()
    if content_range and session.bytes_received and session.bytes_received > 0:
        new_size = storage.append_bytes(session.storage_key, body)
    else:
        path = to_absolute_path(session.storage_key)
        ensure_dir(path)
        if content_range and "bytes " in content_range:
            if path.exists() and path.stat().st_size > 0:
                new_size = storage.append_bytes(session.storage_key, body)
            else:
                storage.put_bytes(session.storage_key, body)
                new_size = len(body)
        else:
            storage.put_bytes(session.storage_key, body)
            new_size = len(body)

    session.bytes_received = new_size
    session.status = models.UploadSessionStatus.UPLOADING.value
    db.commit()


def complete(db: Session, user_id: int, session_id: str):
    session = (
        db.query(models.UploadSession)
        .filter(models.UploadSession.id == session_id)
        .first()
    )
    if not session or session.user_id != user_id:
        raise AppError("Upload session not found", code=ErrorCode.UPLOAD_SESSION_NOT_FOUND)

    storage = get_storage()
    if not storage.exists(session.storage_key):
        raise AppError(
            "Upload object not found in storage", code=ErrorCode.UPLOAD_OBJECT_MISSING
        )

    video = db.query(models.Video).filter(models.Video.id == session.video_id).first()
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)

    local_path = storage.ensure_local(session.storage_key)
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(local_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
    except Exception as e:
        raise AppError(
            "Invalid or corrupt video file", code=ErrorCode.VIDEO_INVALID_FILE
        ) from e

    if duration < 1 or duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise AppError(
            "Video duration out of allowed range", code=ErrorCode.UPLOAD_BAD_REQUEST
        )

    video.duration = duration
    video.file_path = session.storage_key
    video.status = models.VideoStatus.PENDING
    session.status = models.UploadSessionStatus.COMPLETED.value
    session.bytes_received = storage.get_size(session.storage_key)

    job = db.query(models.VideoJob).filter_by(upload_id=video.upload_id).first()
    if job:
        job.stage = models.JobStage.QUEUED.value
        job.status = "queued"
        job.message = "Queued for processing"

    db.commit()
    if not job_queue.enqueue_job(video.upload_id, db):
        mark_enqueue_failed_and_raise(db, video.upload_id)
    emit_video_event(db, video, "video.created")
    return video
