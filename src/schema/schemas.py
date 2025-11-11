from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator
import re


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=1, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        if v.startswith("_") or v.startswith("-") or v.endswith("_") or v.endswith("-"):
            raise ValueError("Username cannot start or end with underscore or hyphen")
        if "__" in v or "--" in v:
            raise ValueError(
                "Username cannot contain consecutive underscores or hyphens"
            )
        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v):
        # Basic regex for email format validation
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v


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
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    duration: Optional[float] = Field(None, gt=0, le=43200)  # Max 12 hours

    @field_validator("title")
    @classmethod
    def validate_title_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty or just whitespace")
        # Prevent excessive special characters
        if len(re.findall(r"[^a-zA-Z0-9\s]", v)) > len(v) * 0.5:
            raise ValueError("Title contains too many special characters")
        # XSS prevention
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None  # Convert empty strings to None
            # XSS prevention
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
        if v is not None and v > 43200:  # 12 hours
            raise ValueError("Video duration cannot exceed 12 hours")
        return v


class VideoCreate(VideoBase):
    file_path: str

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v):
        # Allow "temp" as a placeholder during upload process
        if v == "temp":
            return v
        # Prevent directory traversal
        if '..' in v or v.startswith('/'):
            raise ValueError("Invalid file path")
        # Allow only specific extensions
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError("Unsupported video file format")
        return v


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

    @field_validator("upload_id")
    @classmethod
    def validate_upload_id(cls, v):
        if not re.match(r"^[A-Za-z0-9]{8,12}$", v):
            raise ValueError("Invalid upload ID format")
        return v

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

    @field_validator("name")
    @classmethod
    def validate_playlist_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Playlist name cannot be empty")
        # Prevent names that are just numbers or special chars
        if re.match(r"^[^a-zA-Z]*$", v):
            raise ValueError("Playlist name must contain at least one letter")
        # XSS prevention
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
        return v


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
