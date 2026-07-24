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
