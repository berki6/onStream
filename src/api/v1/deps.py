"""FastAPI dependencies for API v1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from src.infrastructure.db.session import get_db
from src.core.security.api_keys import hash_api_key
from src.core.security.tokens import decode_token
from src.infrastructure.db.repositories import user_repository
from src.infrastructure.db import models

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
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
            raise credentials_exception
        user = db.query(models.User).filter(models.User.id == record.user_id).first()
        if not user or not user.is_active:
            raise credentials_exception
        record.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return user

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        username_str: str = str(username)
    except JWTError:
        raise credentials_exception
    user = user_repository.get_by_username(db, username=username_str)
    if user is None:
        raise credentials_exception
    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None
