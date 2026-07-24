from typing import List, Optional

from pydantic import BaseModel, Field


class WebhookEndpointCreate(BaseModel):
    url: str
    events: List[str] = Field(
        default_factory=lambda: ["video.ready", "video.failed", "video.deleted"]
    )
    secret: Optional[str] = None
