from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.v1.responses import api_ok, raise_app_error
from src.application import auth_service
from src.application.errors import AppError
from src.infrastructure.db.session import get_db
from src.core.logger import get_logger
from src.core.rate_limit import check_auth_rate_limit
from src.schemas import (
    APIResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    User,
    UserCreate,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/register", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    check_auth_rate_limit(request)
    try:
        new_user = auth_service.register(db, user)
    except AppError as e:
        raise_app_error(e)
    logger.info(
        f"User '{user.username}' registered successfully with request_id={request.state.request_id}"
    )
    return api_ok(
        request,
        User.model_validate(new_user),
        message="User registered successfully",
    )


@router.post("/login", response_model=APIResponse)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    check_auth_rate_limit(request)
    try:
        tokens = auth_service.login(db, form_data.username, form_data.password)
    except AppError as e:
        headers = {"WWW-Authenticate": "Bearer"} if e.status_code == 401 else None
        from fastapi import HTTPException

        raise HTTPException(
            status_code=e.status_code, detail=e.message, headers=headers
        )
    logger.info(
        f"User '{form_data.username}' logged in successfully with request_id={request.state.request_id}"
    )
    return api_ok(request, tokens, message="Login successful")


@router.post("/token/refresh", response_model=APIResponse)
def refresh_access_token(
    request: Request,
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    check_auth_rate_limit(request)
    try:
        tokens = auth_service.refresh(db, body.refresh_token)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, tokens, message="Token refreshed")


@router.post("/password-reset", response_model=APIResponse)
def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    check_auth_rate_limit(request)
    data = auth_service.request_password_reset(db, body.email)
    return api_ok(
        request,
        data,
        message="If the email exists, a reset token has been issued",
    )


@router.post("/password-reset/confirm", response_model=APIResponse)
def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    check_auth_rate_limit(request)
    try:
        data = auth_service.confirm_password_reset(db, body.token, body.new_password)
    except AppError as e:
        raise_app_error(e)
    return api_ok(request, data, message="Password updated successfully")
