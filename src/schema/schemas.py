from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    created_at: datetime

    class ConfigDict:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class VideoStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    ERROR = "ERROR"
    DELETED = "DELETED"


class VideoBase(BaseModel):
    title: str
    description: Optional[str] = None
    duration: Optional[float] = None


class VideoCreate(VideoBase):
    file_path: str


class Video(VideoBase):
    upload_id: str
    user_id: int
    file_path: str
    hls_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: VideoStatus
    is_public: bool = False

    class ConfigDict:
        from_attributes = True


class VideoResponse(Video):
    pass


class VideoJobBase(BaseModel):
    upload_id: str
    status: str = "processing"
    progress: int = 0
    eta: int = 0
    message: Optional[str] = None


class VideoJobCreate(VideoJobBase):
    pass


class VideoJob(VideoJobBase):
    created_at: datetime
    updated_at: Optional[datetime] = None

    class ConfigDict:
        from_attributes = True


class VideoJobResponse(VideoJob):
    pass
