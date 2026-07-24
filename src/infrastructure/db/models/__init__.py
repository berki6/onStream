"""Import all models so SQLAlchemy relationships resolve."""

from src.infrastructure.db.base import (
    Base,
    JobStage,
    JobType,
    UploadSessionStatus,
    VideoStatus,
)
from src.infrastructure.db.models.api_key import ApiKey
from src.infrastructure.db.models.idempotency import IdempotencyRecord
from src.infrastructure.db.models.job import QueuedJob, VideoJob
from src.infrastructure.db.models.live_stream import LiveStream
from src.infrastructure.db.models.playlist import Playlist, PlaylistVideo
from src.infrastructure.db.models.upload_session import UploadSession
from src.infrastructure.db.models.user import User
from src.infrastructure.db.models.video import Video, VideoEmbedding, VideoView
from src.infrastructure.db.models.webhook import WebhookDelivery, WebhookEndpoint

__all__ = [
    "Base",
    "VideoStatus",
    "JobStage",
    "JobType",
    "UploadSessionStatus",
    "User",
    "Video",
    "VideoView",
    "VideoEmbedding",
    "LiveStream",
    "Playlist",
    "PlaylistVideo",
    "VideoJob",
    "QueuedJob",
    "UploadSession",
    "WebhookEndpoint",
    "WebhookDelivery",
    "ApiKey",
    "IdempotencyRecord",
]
