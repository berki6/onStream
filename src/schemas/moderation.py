from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ModerationReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    make_public: Optional[bool] = None


class SearchResultItem(BaseModel):
    upload_id: str
    title: str
    description: Optional[str] = None
    score: float = 0.0
    status: Optional[str] = None


class SearchResponse(BaseModel):
    mode: str
    q: str
    results: List[SearchResultItem] = Field(default_factory=list)
    semantic_available: bool = True
    provider: Optional[str] = None
    indexed_videos: int = 0
    reason: Optional[str] = None
    skipped_incompatible: int = 0


class SearchCapabilities(BaseModel):
    semantic_available: bool
    provider: str
    indexed_videos: int = 0
    reason: Optional[str] = None
