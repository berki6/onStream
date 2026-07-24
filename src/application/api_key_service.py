"""API key application service (no FastAPI)."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.core.security.api_keys import generate_api_key
from src.infrastructure.db import models
from src.schemas.api_key import ApiKeyCreate


def create_key(db: Session, user_id: int, body: ApiKeyCreate) -> Dict[str, Any]:
    raw, prefix, key_hash = generate_api_key()
    record = models.ApiKey(
        user_id=user_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes or "upload,read,webhooks",
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "name": record.name,
        "key_prefix": prefix,
        "api_key": raw,
        "scopes": record.scopes,
    }


def list_keys(db: Session, user_id: int) -> List[Dict[str, Any]]:
    keys = db.query(models.ApiKey).filter(models.ApiKey.user_id == user_id).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "scopes": k.scopes,
            "is_active": k.is_active,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at,
        }
        for k in keys
    ]


def revoke_key(db: Session, user_id: int, key_id: int) -> None:
    record = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.id == key_id, models.ApiKey.user_id == user_id)
        .first()
    )
    if not record:
        raise AppError("API key not found", code="not_found", status_code=404)
    record.is_active = False
    db.commit()
