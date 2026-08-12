from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base, JobStage


class VideoJob(Base):
    __tablename__ = "video_jobs"

    upload_id = Column(String(12), primary_key=True)
    status = Column(String, default="queued")
    stage = Column(String(32), default=JobStage.QUEUED.value, index=True)
    progress = Column(Integer, default=0)
    eta = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    cancel_requested = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<VideoJob(upload_id='{self.upload_id}', stage='{self.stage}', "
            f"progress={self.progress}%)>"
        )


class QueuedJob(Base):
    __tablename__ = "queued_jobs"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(String(12), nullable=False, index=True)
    queue_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    job_type = Column(String(32), default="transcode", nullable=False, index=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_queued_jobs_status_queue", "status", "queue_name"),
        Index("idx_queued_jobs_upload_id", "upload_id"),
        Index("idx_queued_jobs_upload_type", "upload_id", "job_type", "status"),
    )
