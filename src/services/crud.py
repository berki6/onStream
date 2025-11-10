from sqlalchemy.orm import Session
from src.schema import models, schemas
from src.core.logger import get_logger
from typing import Optional

logger = get_logger(__name__)


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, user: schemas.UserCreate):
    from src.core.auth import get_password_hash

    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Created user: {user.username}")
    return db_user


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_videos_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_video(db: Session, video: schemas.VideoCreate, user_id: int):
    from src.utils.upload_id import generate_unique_upload_id

    # Generate unique upload_id
    upload_id = generate_unique_upload_id(db)

    db_video = models.Video(**video.dict(), user_id=user_id, upload_id=upload_id)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    logger.info(
        f"Created video: upload_id '{db_video.upload_id}', title '{video.title}' for user ID {user_id}"
    )
    return db_video


def get_video(db: Session, video_id: int):
    return db.query(models.Video).filter(models.Video.id == video_id).first()


def get_video_by_upload_id(db: Session, upload_id: str):
    return db.query(models.Video).filter(models.Video.upload_id == upload_id).first()


def delete_video_by_upload_id(db: Session, upload_id: str):
    video = db.query(models.Video).filter(models.Video.upload_id == upload_id).first()
    if video:
        db.delete(video)
        db.commit()
        logger.info(f"Deleted video upload_id {upload_id}")
    return video


def create_video_job(db: Session, job: schemas.VideoJobCreate):
    db_job = models.VideoJob(**job.dict())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Created video job for upload_id {job.upload_id}")
    return db_job


def get_job_for_video(db: Session, video: models.Video):
    return (
        db.query(models.VideoJob)
        .filter(models.VideoJob.upload_id == video.upload_id)
        .first()
    )
