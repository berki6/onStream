"""Auth application service (no FastAPI)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from jose import JWTError
from sqlalchemy.orm import Session

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
        raise AppError("Username already registered", code="username_taken", status_code=400)
    if user_repository.get_by_email(db, email=user.email):
        raise AppError("Email already registered", code="email_taken", status_code=400)
    return user_repository.create(db, user)


def login(db: Session, username: str, password: str) -> Dict[str, Any]:
    user = user_repository.get_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise AppError(
            "Incorrect username or password",
            code="invalid_credentials",
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
            raise AppError("Invalid refresh token", code="invalid_token", status_code=401)
    except JWTError as e:
        raise AppError("Invalid refresh token", code="invalid_token", status_code=401) from e

    user = user_repository.get_by_username(db, username=str(username))
    if not user or not user.is_active:
        raise AppError("Invalid refresh token", code="invalid_token", status_code=401)

    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def request_password_reset(db: Session, email: str) -> Dict[str, Any]:
    """Always succeeds to avoid email enumeration. May include token in non-prod."""
    user = user_repository.get_by_email(db, email=email)
    data: Dict[str, Any] = {"requested": True}
    if user:
        token = create_password_reset_token(user.email)
        if settings.ENV != "production" or settings.DEBUG:
            data["reset_token"] = token
            data["note"] = "Token included because ENV is not production (or DEBUG)."
    return data


def confirm_password_reset(db: Session, token: str, new_password: str) -> Dict[str, Any]:
    try:
        payload = decode_token(token, expected_type="password_reset")
        email = payload.get("sub")
        if not email:
            raise AppError("Invalid reset token", code="invalid_token", status_code=400)
    except JWTError as e:
        raise AppError(
            "Invalid or expired reset token", code="invalid_token", status_code=400
        ) from e

    user = user_repository.get_by_email(db, email=str(email))
    if not user:
        raise AppError(
            "Invalid or expired reset token", code="invalid_token", status_code=400
        )

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"reset": True}
