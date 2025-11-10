from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class VideoStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


class VideoBase(BaseModel):
    title: str
    duration: Optional[float] = None


class VideoCreate(VideoBase):
    pass


class Video(VideoBase):
    id: int
    user_id: int
    file_path: str
    hls_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    upload_date: datetime
    status: VideoStatus

    class Config:
        from_attributes = True


class VideoResponse(Video):
    pass
