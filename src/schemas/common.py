from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    success: bool = True
    data: Any
    message: Optional[str] = None
    request_id: str
    timestamp: datetime
    api_version: str = "v1"


class PaginatedResponse(APIResponse):
    data: List[Any]
    pagination: dict = Field(
        default_factory=lambda: {
            "total_count": 0,
            "page": 1,
            "per_page": 100,
            "has_more": False,
        }
    )


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[List[dict]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody
    request_id: str
    timestamp: datetime
    api_version: str = "v1"
