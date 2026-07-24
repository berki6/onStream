"""Direct upload session routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import upload_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse, DirectUploadCreate, Video

router = APIRouter()


@router.post("/", response_model=APIResponse)
@router.post("", response_model=APIResponse)
def create_upload_session(
    request: Request,
    response: Response,
    body: DirectUploadCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    try:
        data, code, replay = upload_service.create_session(
            db, current_user.id, body, idempotency_key=idempotency_key
        )
    except AppError as e:
        raise_app_error(e)
    response.status_code = code if replay else status.HTTP_201_CREATED
    message = "Idempotent replay" if replay else "Upload session created"
    return api_ok(request, data, message=message)


@router.put("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_content(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    body = await request.body()
    try:
        upload_service.append_content(
            db,
            current_user.id,
            session_id,
            body,
            content_range=request.headers.get("Content-Range"),
        )
    except AppError as e:
        raise_app_error(e)
    return Response(status_code=204)


@router.post("/{session_id}/complete", response_model=APIResponse)
def complete_upload(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        video = upload_service.complete(db, current_user.id, session_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        Video.model_validate(video),
        message="Upload completed; processing queued",
    )
