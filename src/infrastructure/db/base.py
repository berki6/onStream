from enum import Enum as PyEnum

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class VideoStatus(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    ERROR = "ERROR"
    DELETED = "DELETED"


class JobStage(PyEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    TRANSCODING = "transcoding"
    PACKAGING = "packaging"
    READY = "ready"
    ERROR = "error"
    CANCELLED = "cancelled"


class UploadSessionStatus(PyEnum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
