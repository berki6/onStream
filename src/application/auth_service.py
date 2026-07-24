"""Auth application service (no FastAPI)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from jose import JWTError
from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings
from src.core.security.passwords import get_password_hash, verify_password
from src.core.security.tokens import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
)
from src.infrastructure.db.repositories import user_repository
from src.schemas.auth import UserCreate


def register(db: Session, user: UserCreate):
    if user_repository.get_by_username(db, username=user.username):
        raise AppError("Username already registered", code=ErrorCode.AUTH_USERNAME_TAKEN, status_code=400)
    if user_repository.get_by_email(db, email=user.email):
        raise AppError("Email already registered", code=ErrorCode.AUTH_EMAIL_TAKEN, status_code=400)
    return user_repository.create(db, user)


def login(db: Session, username: str, password: str) -> Dict[str, Any]:
    user = user_repository.get_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise AppError(
            "Incorrect username or password",
            code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            status_code=401,
        )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def refresh(db: Session, refresh_token: str) -> Dict[str, Any]:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
        username = payload.get("sub")
        if not username:
            raise AppError("Invalid refresh token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=401)
    except JWTError as e:
        raise AppError("Invalid refresh token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=401) from e

    user = user_repository.get_by_username(db, username=str(username))
    if not user or not user.is_active:
        raise AppError("Invalid refresh token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=401)

    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def request_password_reset(db: Session, email: str) -> Dict[str, Any]:
    """Always succeeds to avoid email enumeration. May include token in non-prod."""
    from src.core.logger import get_logger
    from src.infrastructure.email import get_email_sender

    logger = get_logger(__name__)
    user = user_repository.get_by_email(db, email=email)
    data: Dict[str, Any] = {"requested": True}
    if user:
        token = create_password_reset_token(user.email)
        base = settings.PUBLIC_API_BASE_URL.rstrip("/")
        reset_url = f"{base}/v1/auth/password-reset/confirm"
        body = (
            f"A password reset was requested for your OnStream account.\n\n"
            f"Use this token with POST {reset_url}:\n\n{token}\n\n"
            f"If you did not request this, you can ignore this message.\n"
        )
        try:
            get_email_sender().send(
                to=user.email,
                subject="OnStream password reset",
                body_text=body,
            )
        except Exception as exc:
            # Do not leak delivery failures to the client; always log for ops.
            logger.error(
                "password_reset_email_failed to=%s error=%s",
                user.email,
                exc,
            )
        # Never return reset tokens in production (even if DEBUG=true).
        if settings.ENV != "production":
            data["reset_token"] = token
            data["note"] = "Token included because ENV is not production."
    return data

def confirm_password_reset(db: Session, token: str, new_password: str) -> Dict[str, Any]:
    try:
        payload = decode_token(token, expected_type="password_reset")
        email = payload.get("sub")
        if not email:
            raise AppError("Invalid reset token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=400)
    except JWTError as e:
        raise AppError(
            "Invalid or expired reset token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=400
        ) from e

    user = user_repository.get_by_email(db, email=str(email))
    if not user:
        raise AppError(
            "Invalid or expired reset token", code=ErrorCode.AUTH_INVALID_TOKEN, status_code=400
        )

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"reset": True}
