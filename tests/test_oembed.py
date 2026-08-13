"""oEmbed 1.0 (bare JSON) + public video card + share peek (no view burn)."""

from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient

from src.application.visibility import apply_visibility
from src.core.security.passwords import get_password_hash
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.infrastructure.db.session import get_db
from src.main import app
from tests.conftest import override_get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _user(db, name: str):
    user = models.User(
        username=name,
        email=f"{name}@example.com",
        hashed_password=get_password_hash("testpass"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _video(db, user, upload_id: str, **kw):
    video = models.Video(
        upload_id=upload_id,
        user_id=user.id,
        title=kw.pop("title", "Embed Clip"),
        description=kw.pop("description", "desc"),
        file_path="data/uploads/x.mp4",
        hls_path=f"data/hls/{upload_id}/master.m3u8",
        status=kw.pop("status", VideoStatus.READY),
        duration=kw.pop("duration", 60.0),
        is_public=False,
        visibility="private",
        **kw,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def _login(username: str) -> str:
    r = client.post("/v1/auth/login", data={"username": username, "password": "testpass"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def test_oembed_public_video_bare_json(db_session):
    user = _user(db_session, "oempub")
    video = _video(
        db_session,
        user,
        "oemPubXY",
        title="Public Reel",
        storyboard_path="data/hls/oemPubXY/storyboard.jpg",
    )
    apply_visibility(video, visibility="public")
    db_session.commit()

    watch = "http://localhost:8000/demo/watch/?v=oemPubXY"
    r = client.get("/v1/oembed", params={"url": watch})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "success" not in body
    assert body["type"] == "video"
    assert body["version"] == "1.0"
    assert body["title"] == "Public Reel"
    assert "oemPubXY" in body["html"]
    assert "embed=1" in body["html"]
    assert body["thumbnail_url"].endswith("/v1/playback/oemPubXY/storyboard.jpg")
    assert body["duration"] == 60.0

    card = client.get("/v1/public/videos/oemPubXY")
    assert card.status_code == 200
    assert card.json()["data"]["title"] == "Public Reel"
    assert card.json()["data"]["playback_url"].endswith("/oemPubXY/master.m3u8")


def test_oembed_private_video_not_found(db_session):
    user = _user(db_session, "oemprv")
    _video(db_session, user, "oemPrvXY", title="Secret")
    r = client.get(
        "/v1/oembed",
        params={"url": "http://localhost:8000/demo/watch/?v=oemPrvXY"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "OEMBED_NOT_FOUND"

    card = client.get("/v1/public/videos/oemPrvXY")
    assert card.status_code == 404


def test_oembed_share_peek_does_not_burn_views(db_session):
    user = _user(db_session, "oemshr")
    video = _video(db_session, user, "oemShrXY", title="Shared Reel")
    token = _login("oemshr")
    created = client.post(
        "/v1/share-links/",
        json={"video_id": video.upload_id, "expires_in_seconds": 3600, "max_views": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    public_id = data["public_id"]
    share_token = data["token"]
    watch = f"http://localhost:8000/demo/watch/?s={public_id}&t={share_token}"

    r = client.get("/v1/oembed", params={"url": watch})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Shared Reel"
    assert "thumbnail_url" not in body
    assert public_id in body["html"]

    listed = client.get(
        "/v1/share-links/",
        params={"video_id": video.upload_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.json()["data"][0]["view_count"] == 0

    peek = client.post(
        f"/v1/share-links/{public_id}/peek",
        json={"token": share_token},
    )
    assert peek.status_code == 200, peek.text
    assert peek.json()["data"]["title"] == "Shared Reel"
    listed = client.get(
        "/v1/share-links/",
        params={"video_id": video.upload_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.json()["data"][0]["view_count"] == 0

    bad = client.get(
        "/v1/oembed",
        params={
            "url": f"http://localhost:8000/demo/watch/?s={public_id}&t=not-the-token-value"
        },
    )
    assert bad.status_code == 404
    assert bad.json()["error"]["code"] == "OEMBED_NOT_FOUND"


def test_oembed_rejects_foreign_host_and_xml(db_session):
    evil = "http://evil.example/demo/watch/?v=oemPubXY"
    r = client.get("/v1/oembed", params={"url": evil})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "OEMBED_NOT_FOUND"

    r = client.get(
        "/v1/oembed",
        params={"url": "http://localhost:8000/demo/watch/?v=oemPubXY", "format": "xml"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "OEMBED_BAD_REQUEST"


def test_oembed_unlisted_watch_url(db_session):
    user = _user(db_session, "oemunl")
    video = _video(db_session, user, "oemUnXYQ", title="Unlisted Reel")
    apply_visibility(video, visibility="unlisted")
    db_session.commit()
    encoded = quote("http://127.0.0.1:8000/demo/watch/?v=oemUnXYQ", safe="")
    r = client.get(f"/v1/oembed?url={encoded}")
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Unlisted Reel"
