"""Job routes nested under videos.

Path param ``video_id`` is the public ``upload_id`` (8-char alphanumeric).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import job_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse, JobActionRequest, VideoJob

router = APIRouter()


@router.get("/{video_id}/jobs/latest", response_model=APIResponse)
def get_latest_job(
    request: Request,
    video_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        job = job_service.get_latest(db, video_id, current_user.id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        VideoJob.model_validate(job),
        message="Job status retrieved successfully",
    )


@router.post("/{video_id}/jobs", response_model=APIResponse)
def apply_job_action(
    request: Request,
    video_id: str,
    body: JobActionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """``video_id`` is the public upload_id (8-char alphanumeric)."""
    try:
        job = job_service.apply_action(db, video_id, current_user.id, body.action)
    except AppError as e:
        raise_app_error(e)
    msg = "Job re-queued" if body.action == "retry" else "Cancel requested"
    return api_ok(request, VideoJob.model_validate(job), message=msg)
