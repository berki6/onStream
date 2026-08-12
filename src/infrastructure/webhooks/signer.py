"""Webhook payload signing."""

from __future__ import annotations

import hashlib
import hmac

WEBHOOK_EVENTS = {
    # VOD
    "video.created",
    "video.ready",
    "video.failed",
    "video.deleted",
    "video.quarantined",
    "video.captions_ready",
    "video.quality",
    # Live (Mux-shaped lifecycle)
    "live.created",
    "live.started",
    "live.idle",
    "live.ended",
}


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
