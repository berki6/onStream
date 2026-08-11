"""Webhook endpoint application service (no FastAPI)."""

from __future__ import annotations

import secrets
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db import models
from src.infrastructure.webhooks.signer import WEBHOOK_EVENTS
from src.schemas.webhook import WebhookEndpointCreate


def _normalize_events(events: List[str] | str) -> List[str]:
    if isinstance(events, str):
        items = [e.strip() for e in events.split(",") if e.strip()]
    else:
        items = [str(e).strip() for e in events if str(e).strip()]
    if not items:
        raise AppError(
            "At least one webhook event is required",
            code=ErrorCode.VALIDATION_BAD_REQUEST,
        )
    unknown = sorted({e for e in items if e != "*" and e not in WEBHOOK_EVENTS})
    if unknown:
        raise AppError(
            f"Unknown webhook event(s): {', '.join(unknown)}",
            code=ErrorCode.VALIDATION_BAD_REQUEST,
        )
    return items


def create_endpoint(db: Session, user_id: int, body: WebhookEndpointCreate) -> Dict[str, Any]:
    secret = body.secret or secrets.token_urlsafe(32)
    event_list = _normalize_events(body.events)
    events = ",".join(event_list)
    ep = models.WebhookEndpoint(
        user_id=user_id,
        url=str(body.url),
        secret=secret,
        events=events,
        is_active=True,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {
        "id": ep.id,
        "url": ep.url,
        "events": ep.events.split(","),
        "secret": secret,
        "is_active": ep.is_active,
    }


def list_endpoints(db: Session, user_id: int) -> List[Dict[str, Any]]:
    eps = (
        db.query(models.WebhookEndpoint)
        .filter(models.WebhookEndpoint.user_id == user_id)
        .all()
    )
    return [
        {
            "id": e.id,
            "url": e.url,
            "events": e.events.split(","),
            "is_active": e.is_active,
            "created_at": e.created_at,
        }
        for e in eps
    ]


def delete_endpoint(db: Session, user_id: int, endpoint_id: int) -> None:
    ep = (
        db.query(models.WebhookEndpoint)
        .filter(
            models.WebhookEndpoint.id == endpoint_id,
            models.WebhookEndpoint.user_id == user_id,
        )
        .first()
    )
    if not ep:
        raise AppError("Webhook not found", code=ErrorCode.WEBHOOK_NOT_FOUND)
    db.delete(ep)
    db.commit()
