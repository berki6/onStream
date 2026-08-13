"""Moderation review routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, api_page, raise_app_error
from src.application import moderation_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.application.media_urls import video_payload
from src.schemas import APIResponse, ModerationReviewRequest

router = APIRouter()


@router.get("/queue", response_model=APIResponse)
def list_quarantine_queue(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    videos, total = moderation_service.list_quarantined(
        db, current_user.id, skip=skip, limit=limit
    )
    return api_page(
        request,
        [video_payload(v) for v in videos],
        total_count=total,
        skip=skip,
        limit=limit,
        message=f"Retrieved {len(videos)} quarantined videos",
    )


@router.post("/{video_id}/review", response_model=APIResponse)
def review_video(
    request: Request,
    video_id: str,
    body: ModerationReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        video = moderation_service.review(
            db,
            current_user.id,
            video_id,
            action=body.action,
            make_public=body.make_public,
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        video_payload(video),
        message=f"Moderation review: {body.action}",
    )
