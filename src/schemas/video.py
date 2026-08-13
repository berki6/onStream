import re
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    ERROR = "ERROR"
    DELETED = "DELETED"
    QUARANTINED = "QUARANTINED"


class VideoBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    duration: Optional[float] = Field(None, gt=0, le=43200)  # Max 12 hours

    @field_validator("title")
    @classmethod
    def validate_title_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty or just whitespace")
        if len(re.findall(r"[^a-zA-Z0-9\s]", v)) > len(v) * 0.5:
            raise ValueError("Title contains too many special characters")
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            v = re.sub(r"<[^>]+>", "", v)
            v = re.sub(
                r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL
            )
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Duration must be positive")
        if v is not None and v > 43200:
            raise ValueError("Video duration cannot exceed 12 hours")
        return v


class VideoCreate(VideoBase):
    file_path: str

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v):
        if v == "temp":
            return v
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid file path")
        allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError("Unsupported video file format")
        return v


class Video(VideoBase):
    upload_id: str
    user_id: int
    file_path: str
    hls_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    storyboard_path: Optional[str] = None
    storyboard_vtt_path: Optional[str] = None
    caption_vtt_path: Optional[str] = None
    transcript_path: Optional[str] = None
    detected_language: Optional[str] = None
    chapters_json: Optional[str] = None
    suggested_title: Optional[str] = None
    suggested_tags: Optional[str] = None
    moderation_score: Optional[float] = None
    quality_score: Optional[float] = None
    moderation_labels: Optional[str] = None
    quarantined_at: Optional[datetime] = None
    preview_clip_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: VideoStatus
    is_public: bool = False
    visibility: str = "private"
    source: str = "upload"
    live_stream_id: Optional[str] = None
    storyboard_url: Optional[str] = None
    storyboard_vtt_url: Optional[str] = None
    captions_url: Optional[str] = None

    @field_validator("upload_id")
    @classmethod
    def validate_upload_id(cls, v):
        if not re.match(r"^[A-Za-z0-9]{8,12}$", v):
            raise ValueError("Invalid upload ID format")
        return v

    @field_validator(
        "file_path",
        "hls_path",
        "thumbnail_path",
        "storyboard_path",
        "storyboard_vtt_path",
        "caption_vtt_path",
        "transcript_path",
        "preview_clip_path",
        mode="before",
    )
    @classmethod
    def normalize_path(cls, v):
        if v and isinstance(v, str):
            return v.replace("\\", "/")
        return v

    model_config = ConfigDict(from_attributes=True)


class VideoResponse(Video):
    pass


class VideoUpdate(BaseModel):
    """Partial update for title, description, and/or visibility."""

    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_public: Optional[bool] = None
    visibility: Optional[Literal["private", "unlisted", "public"]] = None

    @field_validator("title")
    @classmethod
    def validate_title_content(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty or just whitespace")
        if len(re.findall(r"[^a-zA-Z0-9\s]", v)) > len(v) * 0.5:
            raise ValueError("Title contains too many special characters")
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            v = re.sub(r"<[^>]+>", "", v)
            v = re.sub(
                r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL
            )
        return v


class VideoVisibilityUpdate(BaseModel):
    """Compatibility alias body for visibility-only updates."""

    is_public: bool
    visibility: Optional[Literal["private", "unlisted", "public"]] = None


class VideoJobBase(BaseModel):
    upload_id: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    eta: int = 0
    message: Optional[str] = None
    error_code: Optional[str] = None


class VideoJobCreate(VideoJobBase):
    pass


class VideoJob(VideoJobBase):
    cancel_requested: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VideoJobResponse(VideoJob):
    pass


class PlaybackTokenCreate(BaseModel):
    expires_in: Optional[int] = None
    type: Literal["playback"] = "playback"
    clip_start: Optional[float] = Field(None, ge=0)
    clip_end: Optional[float] = Field(None, ge=0)


class PlaybackTokenResponse(BaseModel):
    token: str
    expires_in: int
    playback_url: str
    clip_start: Optional[float] = None
    clip_end: Optional[float] = None


class JobActionRequest(BaseModel):
    action: Literal["retry", "cancel"]
