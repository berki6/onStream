"""Video highlight persistence."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.infrastructure.db import models


def get_by_public_id(db: Session, public_id: str) -> Optional[models.VideoHighlight]:
    return (
        db.query(models.VideoHighlight)
        .filter(models.VideoHighlight.public_id == public_id)
        .first()
    )


def list_for_video(db: Session, video_id: int) -> List[models.VideoHighlight]:
    return (
        db.query(models.VideoHighlight)
        .filter(models.VideoHighlight.video_id == video_id)
        .order_by(models.VideoHighlight.start_seconds.asc())
        .all()
    )


def count_for_video(db: Session, video_id: int) -> int:
    return (
        db.query(models.VideoHighlight)
        .filter(models.VideoHighlight.video_id == video_id)
        .count()
    )


def create(db: Session, row: models.VideoHighlight) -> models.VideoHighlight:
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise


def delete(db: Session, row: models.VideoHighlight) -> None:
    db.delete(row)
    db.commit()
