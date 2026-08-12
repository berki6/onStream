"""Watch progress and continue-watching schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProgressUpdate(BaseModel):
    position_seconds: float = Field(..., ge=0)
    duration_seconds: Optional[float] = Field(None, gt=0)


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    upload_id: str
    position_seconds: float
    duration_seconds: Optional[float] = None
    completed: bool
    last_watched_at: Optional[datetime] = None


class ContinueItem(BaseModel):
    upload_id: str
    title: str
    thumbnail_path: Optional[str] = None
    status: str
    position_seconds: float
    duration_seconds: Optional[float] = None
    completed: bool
    progress_ratio: float = 0.0
    last_watched_at: Optional[datetime] = None
