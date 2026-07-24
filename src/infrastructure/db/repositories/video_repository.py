from typing import Any

from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src import schemas
from src.utils.upload_id import generate_unique_upload_id

logger = get_logger(__name__)


def get_by_upload_id(db: Session, upload_id: str):
    return (
        db.query(models.Video)
        .filter(models.Video.upload_id == upload_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .first()
    )


def get_by_id(db: Session, video_id: int):
    return db.query(models.Video).filter(models.Video.id == video_id).first()


def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    total_count = (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .count()
    )
    videos = (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return videos, total_count


def create(db: Session, video: schemas.VideoCreate, user_id: int):
    upload_id = generate_unique_upload_id(db)
    db_video = models.Video(**video.model_dump(), user_id=user_id, upload_id=upload_id)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    logger.info(
        f"Created video: upload_id '{db_video.upload_id}', title '{video.title}' for user ID {user_id}"
    )
    return db_video


def soft_delete(db: Session, upload_id: str):
    video = db.query(models.Video).filter(models.Video.upload_id == upload_id).first()
    if video:
        video.status = VideoStatus.DELETED
        db.commit()
        logger.info(f"Soft deleted video upload_id {upload_id}")
    return video


def update_fields(db: Session, video: models.Video, **fields: Any) -> models.Video:
    for key, value in fields.items():
        setattr(video, key, value)
    db.commit()
    db.refresh(video)
    return video
