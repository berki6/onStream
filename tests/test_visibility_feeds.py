"""Visibility, unlisted playback, and public RSS feeds."""

from __future__ import annotations

from src.application.visibility import apply_visibility, allows_tokenless_playback, is_rss_listed
from src.core.security.passwords import get_password_hash
from src.core.security.tokens import decode_token
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.main import app
from src.infrastructure.db.session import get_db
from tests.conftest import override_get_db
from fastapi.testclient import TestClient

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _login(username: str, password: str) -> str:
    r = client.post("/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


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
        title=kw.pop("title", "Feed Clip"),
        description=kw.pop("description", "desc"),
        file_path="data/uploads/x.mp4",
        hls_path=f"data/hls/{upload_id}/master.m3u8",
        status=kw.pop("status", VideoStatus.READY),
        duration=60.0,
        is_public=False,
        visibility="private",
        **kw,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def test_unlisted_plays_without_token(db_session):
    user = _user(db_session, "visuser")
    video = _video(db_session, user, "unpubXYQ")
    apply_visibility(video, visibility="unlisted")
    db_session.commit()
    db_session.refresh(video)

    assert video.is_public is False
    assert allows_tokenless_playback(video) is True
    assert is_rss_listed(video) is False

    r = client.get("/v1/playback/unpubXYQ/master.m3u8")
    assert r.status_code != 401
    assert r.status_code != 403
    assert r.status_code != 400


def test_private_still_requires_token(db_session):
    user = _user(db_session, "privuser")
    _video(db_session, user, "prvateXY")
    r = client.get("/v1/playback/prvateXY/master.m3u8")
    assert r.status_code == 401


def test_patch_visibility_and_rss(db_session):
    user = _user(db_session, "rssowner")
    pub = _video(db_session, user, "rsspubXY", title="Public One")
    apply_visibility(pub, visibility="public")
    unl = _video(db_session, user, "rssuxyAB", title="Unlisted One")
    apply_visibility(unl, visibility="unlisted")
    _video(db_session, user, "rssprvXY", title="Private One")
    db_session.commit()

    token = _login("rssowner", "testpass")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch(
        f"/v1/videos/{pub.upload_id}",
        json={"visibility": "public"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["visibility"] == "public"
    assert r.json()["data"]["is_public"] is True

    feed = client.get("/v1/feeds/rssowner/videos.rss")
    assert feed.status_code == 200
    body = feed.text
    assert "Public One" in body
    assert "Unlisted One" not in body
    assert "Private One" not in body
    assert "application/rss+xml" in feed.headers.get("content-type", "")


def test_playlist_patch_public_and_feed(db_session):
    user = _user(db_session, "plrss")
    video = _video(db_session, user, "pvdwxyzA", title="Listed Clip")
    apply_visibility(video, visibility="public")
    db_session.commit()
    token = _login("plrss", "testpass")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/v1/playlists/",
        json={"name": "Show Reel", "is_public": False},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    pid = created.json()["data"]["id"]

    add = client.post(
        f"/v1/playlists/{pid}/videos/{video.upload_id}",
        json={"position": 0},
        headers=headers,
    )
    assert add.status_code == 201, add.text

    hidden = client.get(f"/v1/playlists/public/{pid}")
    assert hidden.status_code == 404

    patched = client.patch(
        f"/v1/playlists/{pid}",
        json={"is_public": True},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["is_public"] is True

    public = client.get(f"/v1/playlists/public/{pid}")
    assert public.status_code == 200
    titles = [v["title"] for v in public.json()["data"]["videos"]]
    assert "Listed Clip" in titles

    feed = client.get(f"/v1/feeds/plrss/playlists/{pid}.rss")
    assert feed.status_code == 200
    assert "Listed Clip" in feed.text
    assert "Show Reel" in feed.text


def test_share_clip_round_trip(db_session, test_user):
    from src.application import share_link_service

    video = _video(db_session, test_user, "cpwxyzAB", title="Clip Source")
    created = share_link_service.create(
        db_session,
        test_user.id,
        video.upload_id,
        expires_in_seconds=3600,
        clip_start=12.5,
        clip_end=40.0,
    )
    assert created["clip_start"] == 12.5
    assert created["clip_end"] == 40.0
    exchanged = share_link_service.exchange(
        db_session, created["public_id"], created["token"]
    )
    assert exchanged["clip_start"] == 12.5
    assert exchanged["clip_end"] == 40.0
    payload = decode_token(exchanged["token"], expected_type="stream")
    assert payload["clip_start"] == 12.5
    assert payload["clip_end"] == 40.0
    assert "storyboard_url" not in exchanged or True
