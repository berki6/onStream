import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlaylistBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_playlist_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Playlist name cannot be empty")
        if re.match(r"^[^a-zA-Z]*$", v):
            raise ValueError("Playlist name must contain at least one letter")
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"<script[^>]*>.*?</script>", "", v, flags=re.IGNORECASE | re.DOTALL)
        return v


class PlaylistCreate(PlaylistBase):
    is_public: bool = False


class PlaylistUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_public: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_playlist_name(cls, v):
        if v is None:
            return v
        return PlaylistBase.validate_playlist_name(v)


class Playlist(PlaylistBase):
    id: int
    user_id: int
    is_public: bool = False
    created_at: datetime
    contains_video: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class PlaylistResponse(Playlist):
    videos: List[dict] = []


class PlaylistVideoBase(BaseModel):
    position: int = Field(ge=0)


class PlaylistVideoCreate(PlaylistVideoBase):
    pass


class PlaylistVideo(PlaylistVideoBase):
    id: int
    playlist_id: int
    video_id: int

    model_config = ConfigDict(from_attributes=True)
