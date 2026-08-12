from typing import Any

from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.infrastructure.db import models
from src import schemas

logger = get_logger(__name__)


def get_by_upload_id(db: Session, upload_id: str):
    return (
        db.query(models.VideoJob)
        .filter(models.VideoJob.upload_id == upload_id)
        .first()
    )


def get_for_video(db: Session, video: models.Video):
    return get_by_upload_id(db, video.upload_id)


def create(db: Session, job: schemas.VideoJobCreate):
    data = job.model_dump()
    if "stage" not in data or not data.get("stage"):
        data["stage"] = "queued"
    if not data.get("status"):
        data["status"] = "queued"
    db_job = models.VideoJob(**data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Created video job for upload_id {job.upload_id}")
    return db_job


def update(db: Session, job: models.VideoJob, **fields: Any) -> models.VideoJob:
    for key, value in fields.items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job
