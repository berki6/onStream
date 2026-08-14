"""Named clip-window highlights (no re-encode)."""

from __future__ import annotations

import json

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
        title=kw.pop("title", "Highlight Source"),
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
    r = client.post(
        "/v1/auth/login", data={"username": username, "password": "testpass"}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def test_highlight_crud_and_duplicate_window(db_session):
    user = _user(db_session, "hlowner")
    video = _video(db_session, user, "hghMark2")
    token = _login("hlowner")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"start": 5, "end": 12, "title": "Open"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    row = created.json()["data"]
    assert row["title"] == "Open"
    assert row["start"] == 5.0
    assert row["end"] == 12.0
    assert len(row["public_id"]) == 8
    hid = row["public_id"]

    listed = client.get(
        f"/v1/videos/{video.upload_id}/highlights", headers=headers
    )
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    dup = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"start": 5, "end": 12},
        headers=headers,
    )
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "HIGHLIGHT_BAD_REQUEST"

    tok = client.post(
        f"/v1/videos/{video.upload_id}/highlights/{hid}/tokens",
        json={},
        headers=headers,
    )
    assert tok.status_code == 200, tok.text
    play = tok.json()["data"]
    assert play["clip_start"] == 5.0
    assert play["clip_end"] == 12.0
    assert video.upload_id in play["playback_url"]

    shared = client.post(
        f"/v1/videos/{video.upload_id}/highlights/{hid}/share",
        json={"expires_in_seconds": 3600},
        headers=headers,
    )
    assert shared.status_code == 201, shared.text
    assert shared.json()["data"]["clip_start"] == 5.0
    assert shared.json()["data"]["clip_end"] == 12.0

    public = client.get(f"/v1/highlights/{hid}")
    assert public.status_code == 404
    assert public.json()["error"]["code"] == "HIGHLIGHT_NOT_FOUND"

    deleted = client.delete(
        f"/v1/videos/{video.upload_id}/highlights/{hid}", headers=headers
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True


def test_highlight_public_watch_and_oembed(db_session):
    user = _user(db_session, "hlpub")
    video = _video(db_session, user, "hghPubX2", title="Public Highlight Reel")
    apply_visibility(video, visibility="public")
    db_session.commit()
    token = _login("hlpub")
    created = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"start": 2, "end": 8, "title": "Hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    hid = created.json()["data"]["public_id"]
    watch = created.json()["data"]["watch_url"]
    assert f"/demo/watch/?h={hid}" in watch

    pub = client.get(f"/v1/highlights/{hid}")
    assert pub.status_code == 200, pub.text
    body = pub.json()["data"]
    assert body["title"] == "Hook"
    assert body["start"] == 2.0
    assert f"/v1/playback/{video.upload_id}/master.m3u8?token=" in body["playback_url"]

    oembed = client.get(
        "/v1/oembed",
        params={"url": f"http://localhost:8000/demo/watch/?h={hid}"},
    )
    assert oembed.status_code == 200, oembed.text
    assert oembed.json()["type"] == "video"
    assert hid in oembed.json()["html"]
    assert "embed=1" in oembed.json()["html"]


def test_highlight_from_chapters(db_session):
    user = _user(db_session, "hlch")
    video = _video(
        db_session,
        user,
        "hghChap2",
        chapters_json=json.dumps(
            [
                {"start": 0, "end": 10, "title": "Intro"},
                {"start": 10, "end": 25, "title": "Main"},
            ]
        ),
    )
    token = _login("hlch")
    headers = {"Authorization": f"Bearer {token}"}
    imported = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"from_chapters": True},
        headers=headers,
    )
    assert imported.status_code == 201, imported.text
    rows = imported.json()["data"]
    assert len(rows) == 2
    assert {r["title"] for r in rows} == {"Intro", "Main"}

    again = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"from_chapters": True},
        headers=headers,
    )
    assert again.status_code == 201
    assert again.json()["data"] == []


def test_highlight_requires_ready_and_auth(db_session):
    user = _user(db_session, "hlpend")
    video = _video(db_session, user, "hghPend2", status=VideoStatus.PROCESSING)
    token = _login("hlpend")
    r = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"start": 1, "end": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "HIGHLIGHT_BAD_REQUEST"

    anon = client.post(
        f"/v1/videos/{video.upload_id}/highlights",
        json={"start": 1, "end": 4},
    )
    assert anon.status_code == 401
