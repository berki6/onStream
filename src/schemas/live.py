"""Pydantic schemas for live streams."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
import re


class LiveStreamCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    is_public: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty or just whitespace")
        v = re.sub(r"<[^>]+>", "", v)
        return v


class LiveStreamResponse(BaseModel):
    stream_id: str
    title: str
    status: str
    is_public: bool
    stream_key_prefix: str
    rtmp_url: Optional[str] = None
    playback_url: Optional[str] = None
    hls_path: Optional[str] = None
    abr_hls_path: Optional[str] = None
    webrtc_base: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    archived_upload_id: Optional[str] = None
    archive_playback_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LiveStreamCreateResponse(LiveStreamResponse):
    """Create response includes plaintext stream_key and WHIP/WHEP once."""

    stream_key: str
    whip_url: Optional[str] = None
    whep_url: Optional[str] = None


class LivePlaybackTokenCreate(BaseModel):
    expires_in: Optional[int] = None
    type: Literal["playback"] = "playback"


class LivePlaybackTokenResponse(BaseModel):
    token: str
    expires_in: int
    playback_url: str
    whep_playback_url: str


class MediaMTXAuthRequest(BaseModel):
    """Payload posted by MediaMTX HTTP auth."""

    user: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    ip: Optional[str] = None
    action: str = "publish"
    path: str = ""
    protocol: Optional[str] = None
    id: Optional[str] = None
    query: Optional[str] = None
    userAgent: Optional[str] = None
