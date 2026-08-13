from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import api_key_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse, ApiKeyCreate

router = APIRouter()


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    request: Request,
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = api_key_service.create_key(db, current_user.id, body)
    except AppError as e:
        raise_app_error(e)
    return api_ok(
        request,
        data,
        message="API key created — store the api_key securely; it will not be shown again",
    )


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
def list_api_keys(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = api_key_service.list_keys(db, current_user.id)
    return api_ok(request, data, message="API keys")


@router.delete("/{key_id}", response_model=APIResponse)
def revoke_api_key(
    request: Request,
    key_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = api_key_service.revoke_key(db, current_user.id, key_id)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="API key revoked")
