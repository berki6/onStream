"""Live lifecycle webhook enqueue tests."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from src.infrastructure.db import models
from src.infrastructure.webhooks.delivery import emit_live_event
from src.infrastructure.webhooks.signer import WEBHOOK_EVENTS
from tests.test_live_streams import _auth_token, _create_stream, client


def _subscribe(db: Session, user: models.User, events: str = "*") -> models.WebhookEndpoint:
    ep = models.WebhookEndpoint(
        user_id=user.id,
        url="https://example.test/hooks/onstream",
        secret="test-secret",
        events=events,
        is_active=True,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _deliveries_for(db: Session, endpoint_id: int) -> list[models.WebhookDelivery]:
    return (
        db.query(models.WebhookDelivery)
        .filter(models.WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(models.WebhookDelivery.id)
        .all()
    )


def test_live_webhook_events_are_registered():
    assert {"live.created", "live.started", "live.idle", "live.ended"} <= WEBHOOK_EVENTS


def test_create_publish_revoke_enqueue_live_webhooks(test_user, db_session: Session):
    ep = _subscribe(db_session, test_user, events="live.created,live.started,live.ended")
    token = _auth_token()

    created = _create_stream(token, title="Webhook Live")
    stream_id = created["stream_id"]
    key = created["stream_key"]

    rows = _deliveries_for(db_session, ep.id)
    assert [r.event for r in rows] == ["live.created"]
    payload = json.loads(rows[0].payload)
    assert payload["type"] == "live.created"
    assert payload["data"]["stream_id"] == stream_id
    assert payload["data"]["status"] == "idle"

    auth = client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}", "protocol": "rtmp"},
    )
    assert auth.status_code == 200

    rows = _deliveries_for(db_session, ep.id)
    assert [r.event for r in rows] == ["live.created", "live.started"]
    started = json.loads(rows[1].payload)
    assert started["data"]["status"] == "live"
    assert started["data"]["reason"] == "publish"

    # Second publish auth while already live must not duplicate live.started
    auth2 = client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}", "protocol": "rtmp"},
    )
    assert auth2.status_code == 200
    rows = _deliveries_for(db_session, ep.id)
    assert [r.event for r in rows] == ["live.created", "live.started"]

    deleted = client.delete(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    rows = _deliveries_for(db_session, ep.id)
    assert [r.event for r in rows] == ["live.created", "live.started", "live.ended"]
    ended = json.loads(rows[2].payload)
    assert ended["data"]["status"] == "ended"
    assert ended["data"]["reason"] == "revoked"


def test_unpublish_enqueues_live_idle(test_user, db_session: Session):
    ep = _subscribe(db_session, test_user, events="live.started,live.idle")
    token = _auth_token()
    created = _create_stream(token, title="Idle Hook")
    key = created["stream_key"]

    assert (
        client.post(
            "/v1/live/mediamtx-auth",
            json={"action": "publish", "path": f"live/{key}", "protocol": "rtmp"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/live/mediamtx-auth",
            json={"action": "unpublish", "path": f"live/{key}", "protocol": "rtmp"},
        ).status_code
        == 200
    )

    rows = _deliveries_for(db_session, ep.id)
    assert [r.event for r in rows] == ["live.started", "live.idle"]
    idle = json.loads(rows[1].payload)
    assert idle["data"]["status"] == "idle"
    assert idle["data"]["reason"] == "unpublish"


def test_emit_live_event_payload_shape(test_user, db_session: Session):
    ep = _subscribe(db_session, test_user, events="live.created")
    stream = models.LiveStream(
        stream_id="Abcdefghijkl",
        user_id=test_user.id,
        title="Shape",
        stream_key_hash="x" * 64,
        stream_key_prefix="abcd1234",
        status="idle",
        is_public=False,
    )
    db_session.add(stream)
    db_session.commit()
    db_session.refresh(stream)

    n = emit_live_event(db_session, stream, "live.created", extra={"reason": "test"})
    assert n == 1
    row = _deliveries_for(db_session, ep.id)[0]
    data = json.loads(row.payload)["data"]
    assert data["stream_id"] == "Abcdefghijkl"
    assert data["user_id"] == test_user.id
    assert data["reason"] == "test"
    assert "hls_path" in data
