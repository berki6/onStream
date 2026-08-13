"""Live → VOD archive on revoke."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.infrastructure.db.session import get_db
from src.main import app
from tests.conftest import override_get_db
from tests.test_live_streams import _auth_token, _create_stream

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

PLAYLIST = (
    "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n"
    "#EXTINF:2.0,\nseg0.ts\n"
)


@pytest.fixture(autouse=True)
def _archive_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path / "live")
    monkeypatch.setattr(settings, "VIDEO_HLS_DIR", tmp_path / "hls")
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(settings, "PUBLIC_WEBRTC_BASE_URL", "http://localhost:8889")
    monkeypatch.setattr(settings, "MEDIAMTX_AUTH_SECRET", "")
    monkeypatch.setattr(
        "src.application.live_service.live_record.start_record", lambda *a, **k: None
    )


def _write_archive(stream_id: str) -> None:
    dest = Path(settings.LIVE_HLS_DIR) / stream_id / "archive"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.m3u8").write_text(PLAYLIST, encoding="utf-8")
    (dest / "seg0.ts").write_bytes(b"\x00" * 32)


def test_revoke_promotes_archive_to_vod(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token, title="Archive me")
    stream_id = created["stream_id"]
    key = created["stream_key"]
    client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}"},
    )
    _write_archive(stream_id)

    deleted = client.delete(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    data = deleted.json()["data"]
    assert data["status"] == "ended"
    upload_id = data["archived_upload_id"]
    assert upload_id
    assert upload_id in (data["archive_playback_url"] or "")

    got = client.get(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.json()["data"]["archived_upload_id"] == upload_id

    vod = client.get(
        f"/v1/videos/{upload_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vod.status_code == 200
    body = vod.json()["data"]
    assert body["status"] == "READY"
    assert body["source"] == "live"
    assert body["live_stream_id"] == stream_id
    assert body["title"] == "Archive me"
    assert body["duration"] == 2.0

    master = client.get(
        f"/v1/playback/{upload_id}/master.m3u8",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert master.status_code == 200
    text = master.text
    assert "index.m3u8" in text

    live_master = client.get(
        f"/v1/playback/live/{stream_id}/master.m3u8",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert live_master.status_code == 404


def test_revoke_without_archive_still_ends(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token)
    deleted = client.delete(
        f"/v1/live/{created['stream_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["status"] == "ended"
    assert deleted.json()["data"]["archived_upload_id"] is None


def test_revoke_does_not_promote_sliding_live_window(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token, title="Window copy")
    stream_id = created["stream_id"]
    dest = Path(settings.LIVE_HLS_DIR) / stream_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.m3u8").write_text(PLAYLIST, encoding="utf-8")
    (dest / "seg0.ts").write_bytes(b"\x00" * 32)

    deleted = client.delete(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["archived_upload_id"] is None

