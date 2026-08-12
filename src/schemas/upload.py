from typing import Optional

from pydantic import BaseModel, Field


class DirectUploadCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    content_type: Optional[str] = "video/mp4"
    is_public: bool = False
