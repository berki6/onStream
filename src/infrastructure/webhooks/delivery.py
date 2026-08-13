"""Outbound webhook delivery with HMAC signatures and retries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.webhooks.signer import WEBHOOK_EVENTS, sign_payload

logger = get_logger(__name__)

__all__ = [
    "WEBHOOK_EVENTS",
    "sign_payload",
    "enqueue_event",
    "_deliver_one",
    "process_pending_deliveries",
    "emit_video_event",
    "emit_live_event",
]


def enqueue_event(
    db: Session,
    user_id: int,
    event: str,
    data: dict,
) -> int:
    """Create pending deliveries for all matching active endpoints. Returns count."""
    if event not in WEBHOOK_EVENTS:
        logger.warning(f"Unknown webhook event: {event}")
        return 0

    endpoints = (
        db.query(models.WebhookEndpoint)
        .filter(
            models.WebhookEndpoint.user_id == user_id,
            models.WebhookEndpoint.is_active == True,
        )
        .all()
    )
    count = 0
    payload_obj = {
        "type": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    payload_str = json.dumps(payload_obj, default=str)

    for ep in endpoints:
        subscribed = {e.strip() for e in (ep.events or "").split(",") if e.strip()}
        if event not in subscribed and "*" not in subscribed:
            continue
        delivery = models.WebhookDelivery(
            endpoint_id=ep.id,
            event=event,
            payload=payload_str,
            status="pending",
            attempts=0,
            next_retry_at=datetime.now(timezone.utc),
        )
        db.add(delivery)
        count += 1
    if count:
        db.commit()
    return count


def _deliver_one(db: Session, delivery: models.WebhookDelivery) -> bool:
    endpoint = (
        db.query(models.WebhookEndpoint)
        .filter(models.WebhookEndpoint.id == delivery.endpoint_id)
        .first()
    )
    if not endpoint or not endpoint.is_active:
        delivery.status = "failed"
        delivery.last_error = "Endpoint missing or inactive"
        db.commit()
        return False

    body = delivery.payload.encode("utf-8")
    signature = sign_payload(endpoint.secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-OnStream-Signature": signature,
        "X-OnStream-Event": delivery.event,
        "User-Agent": "OnStream-Webhooks/0.2",
    }
    delivery.attempts = (delivery.attempts or 0) + 1
    try:
        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.3, min=0.3, max=3),
            retry=retry_if_exception_type(
                (httpx.TransportError, httpx.TimeoutException)
            ),
        )
        def _post() -> httpx.Response:
            with httpx.Client(timeout=10.0) as client:
                return client.post(endpoint.url, content=body, headers=headers)

        resp = _post()
        if 200 <= resp.status_code < 300:
            delivery.status = "success"
            delivery.last_error = None
            db.commit()
            return True
        delivery.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        delivery.last_error = str(e)

    # Exponential backoff: 1m, 5m, 25m, then fail
    if delivery.attempts >= 4:
        delivery.status = "failed"
    else:
        delay_minutes = 5 ** (delivery.attempts - 1)
        delivery.status = "pending"
        delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(
            minutes=delay_minutes
        )
    db.commit()
    return False


def process_pending_deliveries(limit: int = 50) -> int:
    """Process due webhook deliveries. Returns successes."""
    db = SessionLocal()
    successes = 0
    try:
        now = datetime.now(timezone.utc)
        pending = (
            db.query(models.WebhookDelivery)
            .filter(
                models.WebhookDelivery.status == "pending",
                models.WebhookDelivery.next_retry_at <= now,
            )
            .order_by(models.WebhookDelivery.id)
            .limit(limit)
            .all()
        )
        for delivery in pending:
            if _deliver_one(db, delivery):
                successes += 1
    finally:
        db.close()
    return successes


def emit_video_event(
    db: Session, video: models.Video, event: str, extra: Optional[dict] = None
):
    data = {
        "upload_id": video.upload_id,
        "video_id": video.id,
        "user_id": video.user_id,
        "title": video.title,
        "status": video.status.value if hasattr(video.status, "value") else video.status,
        "is_public": video.is_public,
        "visibility": getattr(video, "visibility", None),
        "hls_path": video.hls_path,
        "thumbnail_path": video.thumbnail_path,
    }
    if extra:
        data.update(extra)
    return enqueue_event(db, video.user_id, event, data)


def emit_live_event(
    db: Session,
    stream: models.LiveStream,
    event: str,
    extra: Optional[dict] = None,
) -> int:
    """
    Enqueue a live lifecycle webhook for all matching user endpoints.

    Payload always includes stream identity and current status; ``extra`` adds
    transition metadata (e.g. ``reason``).
    """
    data = {
        "stream_id": stream.stream_id,
        "user_id": stream.user_id,
        "title": stream.title,
        "status": stream.status,
        "is_public": stream.is_public,
        "hls_path": stream.hls_path,
        "abr_hls_path": stream.abr_hls_path,
        "started_at": stream.started_at.isoformat() if stream.started_at else None,
        "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
        "archived_upload_id": getattr(stream, "archived_upload_id", None),
    }
    if extra:
        data.update(extra)
    return enqueue_event(db, stream.user_id, event, data)
