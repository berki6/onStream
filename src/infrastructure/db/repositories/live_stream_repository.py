"""Repository for live streams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.infrastructure.db import models

logger = get_logger(__name__)


def get_by_stream_id(db: Session, stream_id: str) -> Optional[models.LiveStream]:
    return (
        db.query(models.LiveStream)
        .filter(models.LiveStream.stream_id == stream_id)
        .first()
    )


def get_by_stream_key_hash(
    db: Session, stream_key_hash: str
) -> Optional[models.LiveStream]:
    return (
        db.query(models.LiveStream)
        .filter(models.LiveStream.stream_key_hash == stream_key_hash)
        .first()
    )


def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    total = (
        db.query(models.LiveStream)
        .filter(models.LiveStream.user_id == user_id)
        .filter(models.LiveStream.status != "ended")
        .count()
    )
    rows = (
        db.query(models.LiveStream)
        .filter(models.LiveStream.user_id == user_id)
        .filter(models.LiveStream.status != "ended")
        .order_by(models.LiveStream.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows, total


def create(
    db: Session,
    *,
    stream_id: str,
    user_id: int,
    title: str,
    stream_key_hash: str,
    stream_key_prefix: str,
    is_public: bool = False,
) -> models.LiveStream:
    row = models.LiveStream(
        stream_id=stream_id,
        user_id=user_id,
        title=title,
        stream_key_hash=stream_key_hash,
        stream_key_prefix=stream_key_prefix,
        status="idle",
        is_public=is_public,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Created live stream %s for user %s", stream_id, user_id)
    return row


def set_live(
    db: Session,
    stream: models.LiveStream,
    *,
    hls_path: Optional[str] = None,
    abr_hls_path: Optional[str] = None,
) -> models.LiveStream:
    stream.status = "live"
    stream.started_at = datetime.now(timezone.utc)
    stream.ended_at = None
    if hls_path is not None:
        stream.hls_path = hls_path
    if abr_hls_path is not None:
        stream.abr_hls_path = abr_hls_path
    db.commit()
    db.refresh(stream)
    return stream


def set_idle(db: Session, stream: models.LiveStream) -> models.LiveStream:
    stream.status = "idle"
    db.commit()
    db.refresh(stream)
    return stream


def revoke(db: Session, stream: models.LiveStream) -> models.LiveStream:
    stream.status = "ended"
    stream.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(stream)
    logger.info("Revoked live stream %s", stream.stream_id)
    return stream


def update_fields(
    db: Session, stream: models.LiveStream, **fields: Any
) -> models.LiveStream:
    for key, value in fields.items():
        setattr(stream, key, value)
    db.commit()
    db.refresh(stream)
    return stream
