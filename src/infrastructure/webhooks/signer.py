"""Webhook payload signing."""

from __future__ import annotations

import hashlib
import hmac

WEBHOOK_EVENTS = {
    "video.created",
    "video.ready",
    "video.failed",
    "video.deleted",
}


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
