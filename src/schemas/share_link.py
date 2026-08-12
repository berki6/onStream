"""Share link schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ShareLinkCreate(BaseModel):
    video_id: str = Field(..., min_length=8, max_length=8, description="upload_id")
    expires_in_seconds: int = Field(86400, ge=60, le=60 * 60 * 24 * 90)
    label: Optional[str] = Field(None, max_length=120)
    max_views: Optional[int] = Field(None, ge=1, le=1_000_000)


class ShareLinkExchange(BaseModel):
    token: str = Field(..., min_length=16, max_length=128)


class ShareLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    video_id: str
    label: Optional[str] = None
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    max_views: Optional[int] = None
    view_count: int = 0
    created_at: Optional[datetime] = None
    active: bool = True


class ShareLinkCreateResponse(ShareLinkResponse):
    """Includes plaintext token once at create time."""

    token: str
    watch_url: str
    share_url: str


class ShareExchangeResponse(BaseModel):
    token: str
    expires_in: int
    playback_url: str
    upload_id: str
    title: str
    expires_at: datetime
