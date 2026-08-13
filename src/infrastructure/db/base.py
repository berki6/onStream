from enum import Enum as PyEnum

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class VideoStatus(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    ERROR = "ERROR"
    DELETED = "DELETED"
    QUARANTINED = "QUARANTINED"


class JobStage(PyEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    TRANSCODING = "transcoding"
    PACKAGING = "packaging"
    READY = "ready"
    ERROR = "error"
    CANCELLED = "cancelled"


class JobType(PyEnum):
    TRANSCODE = "transcode"
    CAPTIONS = "captions"
    CHAPTERS = "chapters"
    MODERATION = "moderation"
    EMBEDDINGS = "embeddings"
    SMART_THUMBNAIL = "smart_thumbnail"
    STORYBOARD = "storyboard"


class UploadSessionStatus(PyEnum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
