"""Media-core tests: stream tokens, webhooks, ABR master playlist helper, uploads."""

import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.core.security.passwords import get_password_hash
from src.core.security.tokens import create_stream_token, create_access_token
from src.infrastructure.db.session import get_db
from src.infrastructure.db import models
from src.infrastructure.webhooks.delivery import sign_payload
from src.infrastructure.media.abr import write_master_playlist
from tests.conftest import TestingSessionLocal, override_get_db
from pathlib import Path


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture
def user_and_token(db_session):
    user = models.User(
        username="p2user",
        email="p2@example.com",
        hashed_password=get_password_hash("Testpass1!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token({"sub": user.username})
    yield user, token
    db_session.delete(user)
    db_session.commit()


def test_write_master_playlist(tmp_path: Path):
    renditions = [
        {"height": 360, "bitrate_k": 800},
        {"height": 720, "bitrate_k": 2800},
    ]
    master = write_master_playlist(tmp_path, renditions)
    text = master.read_text()
    assert "#EXTM3U" in text
    assert "360p/index.m3u8" in text
    assert "720p/index.m3u8" in text
    assert "BANDWIDTH=2800000" in text


def test_stream_token_required_for_private(db_session, user_and_token):
    user, token = user_and_token
    video = models.Video(
        upload_id="abcdEFGH",
        user_id=user.id,
        title="Private",
        file_path="data/uploads/x.mp4",
        hls_path="data/hls/abcdEFGH/master.m3u8",
        status=models.VideoStatus.READY,
        is_public=False,
    )
    db_session.add(video)
    db_session.commit()

    # No auth
    r = client.get("/v1/playback/abcdEFGH/master.m3u8")
    assert r.status_code == 401

    # With owner JWT — may 404 if file missing, but not 401/403
    r2 = client.get(
        "/v1/playback/abcdEFGH/master.m3u8",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code in (200, 404, 500)

    # With stream token
    st = create_stream_token("abcdEFGH")
    r3 = client.get(f"/v1/playback/abcdEFGH/master.m3u8?token={st}")
    assert r3.status_code in (200, 404, 500)


def test_public_stream_no_auth(db_session, user_and_token):
    user, _ = user_and_token
    video = models.Video(
        upload_id="pubVidAB",
        user_id=user.id,
        title="Public",
        file_path="data/uploads/y.mp4",
        hls_path="data/hls/pubVidAB/master.m3u8",
        status=models.VideoStatus.READY,
        is_public=True,
    )
    db_session.add(video)
    db_session.commit()
    r = client.get("/v1/playback/pubVidAB/master.m3u8")
    # Public skips auth; 404 if file absent is fine
    assert r.status_code != 401
    assert r.status_code != 403


def test_webhook_signature():
    secret = "whsec_test"
    body = b'{"type":"video.ready"}'
    sig = sign_payload(secret, body)
    assert sig.startswith("sha256=")
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sig == f"sha256={digest}"


def test_create_webhook_and_api_key(user_and_token):
    user, token = user_and_token
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/v1/webhooks",
        headers=headers,
        json={"url": "https://example.com/hook", "events": ["video.ready"]},
    )
    assert r.status_code == 201
    assert "secret" in r.json()["data"]

    r_del = client.get("/v1/webhooks/deliveries", headers=headers)
    assert r_del.status_code == 200
    assert isinstance(r_del.json()["data"], list)

    r2 = client.post(
        "/v1/api-keys",
        headers=headers,
        json={"name": "ci"},
    )
    assert r2.status_code == 201
    assert r2.json()["data"]["api_key"].startswith("osk_")


def test_direct_upload_session(user_and_token):
    user, token = user_and_token
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"}
    r = client.post(
        "/v1/uploads",
        headers=headers,
        json={"title": "Direct Upload", "is_public": False},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert "session_id" in data
    assert "upload_url" in data
    assert "upload_id" in data

    # Idempotent replay (same key should return same session)
    r2 = client.post(
        "/v1/uploads",
        headers=headers,
        json={"title": "Direct Upload", "is_public": False},
    )
    assert r2.status_code in (200, 201)
    assert r2.json()["data"]["session_id"] == data["session_id"]
    assert r2.json()["message"] in ("Idempotent replay", "Upload session created")


def test_playback_token_endpoint(db_session, user_and_token):
    user, token = user_and_token
    video = models.Video(
        upload_id="toknABCD",
        user_id=user.id,
        title="Tok",
        file_path="data/uploads/z.mp4",
        hls_path="data/hls/toknABCD/master.m3u8",
        status=models.VideoStatus.READY,
        is_public=False,
    )
    db_session.add(video)
    db_session.commit()

    r = client.post(
        "/v1/videos/toknABCD/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "token" in r.json()["data"]
    assert "playback_url" in r.json()["data"]
