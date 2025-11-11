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
    PROCESSING = "PROCESSING"
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


class PlaylistBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PlaylistCreate(PlaylistBase):
    pass


class Playlist(PlaylistBase):
    id: int
    user_id: int
    is_public: bool = False
    created_at: datetime

    class ConfigDict:
        from_attributes = True


class PlaylistResponse(Playlist):
    videos: Optional[list] = []


class PlaylistVideoBase(BaseModel):
    position: int = Field(ge=0)


class PlaylistVideoCreate(PlaylistVideoBase):
    pass


class PlaylistVideo(PlaylistVideoBase):
    id: int
    playlist_id: int
    video_id: int

    class ConfigDict:
        from_attributes = True
