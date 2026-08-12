"""Search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import search_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse

router = APIRouter()


@router.get("/", response_model=APIResponse)
@router.get("", response_model=APIResponse)
def search_videos(
    request: Request,
    q: str = Query(..., min_length=1),
    mode: str = Query("keyword"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = search_service.search(
            db, current_user.id, q=q, mode=mode, limit=limit
        )
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Search results")
