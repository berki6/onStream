"""FastAPI dependencies for API v1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from src.application.api_key_scopes import (
    LAST_USED_MIN_INTERVAL_SECONDS,
    assert_api_key_allowed,
)
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.security.api_keys import hash_api_key
from src.core.security.tokens import decode_token
from src.infrastructure.db import models
from src.infrastructure.db.repositories import user_repository
from src.infrastructure.db.session import get_db

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    credentials_error = AppError(
        "Could not validate credentials",
        code=ErrorCode.AUTH_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )

    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        key_hash = hash_api_key(api_key_header)
        record = (
            db.query(models.ApiKey)
            .filter(models.ApiKey.key_hash == key_hash, models.ApiKey.is_active == True)
            .first()
        )
        if not record:
            raise credentials_error
        user = db.query(models.User).filter(models.User.id == record.user_id).first()
        if not user or not user.is_active:
            raise credentials_error
        assert_api_key_allowed(record.scopes, request.method, request.url.path)
        now = datetime.now(timezone.utc)
        last = record.last_used_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is None or (now - last).total_seconds() >= LAST_USED_MIN_INTERVAL_SECONDS:
            record.last_used_at = now
            db.commit()
            db.refresh(user)
        return user

    if credentials is None:
        raise credentials_error

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        username = payload.get("sub")
        if username is None:
            raise credentials_error
        username_str: str = str(username)
    except JWTError:
        raise credentials_error
    user = user_repository.get_by_username(db, username=username_str)
    if user is None:
        raise credentials_error
    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        return await get_current_user(request, credentials, db)
    except AppError as e:
        if e.code == ErrorCode.AUTH_UNAUTHORIZED:
            return None
        raise
