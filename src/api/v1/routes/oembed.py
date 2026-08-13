"""Public oEmbed + tokenless watch card.

GET /v1/oembed is spec JSON (not the API envelope) so Slack/WordPress
consumers can parse type/html at the document root.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.v1.responses import api_ok, raise_app_error
from src.application import oembed_service
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse

router = APIRouter()


@router.get("/oembed")
@router.get("/oembed/")
def oembed(
    request: Request,
    url: str = Query(..., min_length=8),
    maxwidth: Optional[int] = Query(None, ge=200, le=1280),
    maxheight: Optional[int] = Query(None, ge=113, le=720),
    format: str = Query("json"),
    db: Session = Depends(get_db),
):
    if (format or "json").lower() != "json":
        raise_app_error(
            AppError("Only format=json is supported", code=ErrorCode.OEMBED_BAD_REQUEST)
        )
    try:
        data = oembed_service.resolve(
            db,
            url,
            request_host=request.url.netloc,
            maxwidth=maxwidth,
            maxheight=maxheight,
        )
    except AppError as e:
        raise_app_error(e)
    return JSONResponse(content=data)


@router.get("/public/videos/{video_id}", response_model=APIResponse)
def public_video(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
):
    try:
        data = oembed_service.public_video_card(db, video_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Public video")
