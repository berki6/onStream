from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user
from src.api.v1.responses import api_ok, raise_app_error
from src.application import webhook_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.schemas import APIResponse, WebhookEndpointCreate

router = APIRouter()


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    request: Request,
    body: WebhookEndpointCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        data = webhook_service.create_endpoint(db, current_user.id, body)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Webhook endpoint created")


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
def list_webhooks(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = webhook_service.list_endpoints(db, current_user.id)
    return api_ok(request, data, message="Webhook endpoints")


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        webhook_service.delete_endpoint(db, current_user.id, endpoint_id)
    except AppError as e:
        raise_app_error(e)
