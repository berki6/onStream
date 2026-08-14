"""Live stream API and MediaMTX auth tests (mocked ABR / fake HLS)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.infrastructure.db.session import get_db
from src.infrastructure.media import live_abr
from src.infrastructure.media import live_normalize
from src.main import app
from tests.conftest import override_get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _live_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path / "live")
    monkeypatch.setattr(settings, "VIDEO_HLS_DIR", tmp_path / "hls")
    monkeypatch.setattr(settings, "PUBLIC_RTMP_BASE_URL", "rtmp://localhost:1935/live")
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(settings, "PUBLIC_WEBRTC_BASE_URL", "http://localhost:8889")
    monkeypatch.setattr(settings, "MEDIAMTX_AUTH_SECRET", "")
    live_abr._processes.clear()
    live_normalize._processes.clear()
    live_normalize._ll_processes.clear()
    live_normalize._stops.clear()
    live_normalize._probing.clear()
    yield
    live_abr._processes.clear()
    live_normalize._processes.clear()
    live_normalize._ll_processes.clear()
    live_normalize._stops.clear()
    live_normalize._probing.clear()


def _auth_token():
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _create_stream(token: str, title: str = "Live Test", is_public: bool = False):
    response = client.post(
        "/v1/live/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title, "is_public": is_public},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_create_stream_returns_rtmp_and_key(test_user, db_session: Session):
    token = _auth_token()
    data = _create_stream(token)
    assert data["stream_id"]
    assert len(data["stream_id"]) == 12
    assert data["stream_key"]
    assert data["stream_key_prefix"] == data["stream_key"][:8]
    assert data["rtmp_url"] == "rtmp://localhost:1935/live"
    assert f"/v1/playback/live/{data['stream_id']}/master.m3u8" in data["playback_url"]
    assert data["ll_hls"] is False
    assert data.get("ll_playback_url") in (None, "")
    assert data["status"] == "idle"
    assert data["whip_url"] == f"http://localhost:8889/live/{data['stream_key']}/whip"
    assert data["whep_url"] == f"http://localhost:8889/live/{data['stream_key']}/whep"
    # Plaintext key must not appear on subsequent GET
    get_resp = client.get(
        f"/v1/live/{data['stream_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    body = get_resp.json()["data"]
    assert "stream_key" not in body
    assert "whip_url" not in body
    assert "whep_url" not in body
    assert body.get("webrtc_base") == "http://localhost:8889"


def test_ll_playback_url_only_when_enabled(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", True)
    token = _auth_token()
    data = _create_stream(token, title="LL urls")
    assert data["ll_hls"] is True
    assert f"/v1/playback/live/{data['stream_id']}/ll/master.m3u8" in (
        data["ll_playback_url"] or ""
    )
    tok = client.post(
        f"/v1/live/{data['stream_id']}/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert tok.status_code == 200
    assert f"/ll/master.m3u8?token=" in tok.json()["data"]["ll_playback_url"]


def test_list_get_delete(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token, title="To delete")
    stream_id = created["stream_id"]

    listed = client.get("/v1/live/", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    ids = [r["stream_id"] for r in listed.json()["data"]]
    assert stream_id in ids

    got = client.get(
        f"/v1/live/{stream_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert got.status_code == 200
    assert got.json()["data"]["title"] == "To delete"

    deleted = client.delete(
        f"/v1/live/{stream_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["status"] == "ended"

    # Owner can still fetch ended streams (lab UI after revoke)
    still = client.get(
        f"/v1/live/{stream_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert still.status_code == 200
    assert still.json()["data"]["status"] == "ended"

    # Ended streams drop out of the active list
    listed_after = client.get(
        "/v1/live/", headers={"Authorization": f"Bearer {token}"}
    )
    assert listed_after.status_code == 200
    assert stream_id not in [
        r["stream_id"] for r in listed_after.json()["data"]
    ]

    # Opt-in history for lab UI
    with_ended = client.get(
        "/v1/live/?include_ended=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert with_ended.status_code == 200
    ended_ids = [r["stream_id"] for r in with_ended.json()["data"]]
    assert stream_id in ended_ids
    ended_row = next(r for r in with_ended.json()["data"] if r["stream_id"] == stream_id)
    assert ended_row["status"] == "ended"

def test_mediamtx_auth_accepts_valid_key_rejects_bad(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]

    ok = client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}", "protocol": "rtmp"},
    )
    assert ok.status_code == 200

    # Stream should be live now
    got = client.get(
        f"/v1/live/{created['stream_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.json()["data"]["status"] == "live"

    bad = client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": "live/not-a-real-key", "protocol": "rtmp"},
    )
    assert bad.status_code == 401


def test_playback_requires_token_for_private(test_user, db_session: Session, tmp_path):
    token = _auth_token()
    created = _create_stream(token, is_public=False)
    stream_id = created["stream_id"]
    key = created["stream_key"]

    # Publish so hls_path is set
    client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}"},
    )

    hls_dir = Path(settings.LIVE_HLS_DIR) / f"live/{key}"
    hls_dir.mkdir(parents=True, exist_ok=True)
    (hls_dir / "index.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:2.0,\nseg0.ts\n",
        encoding="utf-8",
    )
    (hls_dir / "seg0.ts").write_bytes(b"\x00" * 16)

    denied = client.get(f"/v1/playback/live/{stream_id}/master.m3u8")
    assert denied.status_code == 401

    tok_resp = client.post(
        f"/v1/live/{stream_id}/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert tok_resp.status_code == 200
    playback_token = tok_resp.json()["data"]["token"]

    ok = client.get(
        f"/v1/playback/live/{stream_id}/master.m3u8",
        params={"token": playback_token},
    )
    assert ok.status_code == 200
    assert b"#EXTM3U" in ok.content


def test_abr_disabled_does_not_spawn(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]

    with patch.object(live_abr, "start_abr", wraps=live_abr.start_abr) as mock_start:
        with patch("src.infrastructure.media.live_abr.subprocess.Popen") as mock_popen:
            client.post(
                "/v1/live/mediamtx-auth",
                json={"action": "publish", "path": f"live/{key}"},
            )
            # authorize_publish only calls start_abr when LIVE_ABR_ENABLED
            mock_start.assert_not_called()
            mock_popen.assert_not_called()


def test_abr_enabled_calls_start(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", True)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    fake_proc = MagicMock()
    fake_proc.poll.return_value = None

    with patch(
        "src.infrastructure.media.live_abr.subprocess.Popen", return_value=fake_proc
    ) as mock_popen:
        with patch("src.infrastructure.media.live_abr.shutil.which", return_value="ffmpeg"):
            client.post(
                "/v1/live/mediamtx-auth",
                json={"action": "publish", "path": f"live/{key}"},
            )
            mock_popen.assert_called_once()
            assert live_abr.abr_running(stream_id)
            cmd = mock_popen.call_args[0][0]
            assert "-rtsp_transport" in cmd
            assert any(str(x).startswith("rtsp://") for x in cmd)

    # Cleanup
    live_abr.stop_abr(stream_id)


def test_normalize_started_when_abr_off(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    with patch.object(live_normalize, "start_normalize") as mock_norm:
        client.post(
            "/v1/live/mediamtx-auth",
            json={"action": "publish", "path": f"live/{key}"},
        )
        mock_norm.assert_called_once_with(stream_id, key)


def test_abr_skips_normalize(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]

    with patch.object(live_normalize, "start_normalize") as mock_norm:
        with patch.object(live_abr, "start_abr") as mock_abr:
            client.post(
                "/v1/live/mediamtx-auth",
                json={"action": "publish", "path": f"live/{key}"},
            )
            mock_abr.assert_called_once()
            mock_norm.assert_not_called()


def test_ll_starts_normalize_with_archive_and_abr(
    test_user, db_session: Session, monkeypatch
):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", True)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    with patch.object(live_normalize, "start_normalize") as mock_norm:
        with patch.object(live_abr, "start_abr") as mock_abr:
            with patch("src.application.live_service.live_record.start_record"):
                client.post(
                    "/v1/live/mediamtx-auth",
                    json={"action": "publish", "path": f"live/{key}"},
                )
                mock_abr.assert_called_once()
                mock_norm.assert_called_once_with(stream_id, key)


def test_archive_skips_sliding_normalize(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    with patch.object(live_normalize, "start_normalize") as mock_norm:
        with patch("src.application.live_service.live_record.start_record") as mock_rec:
            client.post(
                "/v1/live/mediamtx-auth",
                json={"action": "publish", "path": f"live/{key}"},
            )
            mock_norm.assert_not_called()
            mock_rec.assert_called_once_with(stream_id, key)


def test_unpublish_marks_idle_and_stops_abr(test_user, db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", True)
    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch(
        "src.infrastructure.media.live_abr.subprocess.Popen", return_value=fake_proc
    ):
        with patch("src.infrastructure.media.live_abr.shutil.which", return_value="ffmpeg"):
            client.post(
                "/v1/live/mediamtx-auth",
                json={"action": "publish", "path": f"live/{key}"},
            )
            assert live_abr.abr_running(stream_id)

    unpub = client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "unpublish", "path": f"live/{key}"},
    )
    assert unpub.status_code == 200
    assert not live_abr.abr_running(stream_id)

    got = client.get(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.json()["data"]["status"] == "idle"


def test_health_endpoint_owner_only(test_user, db_session: Session, tmp_path):
    token = _auth_token()
    created = _create_stream(token, is_public=True)
    stream_id = created["stream_id"]
    key = created["stream_key"]

    client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}"},
    )
    hls_dir = Path(settings.LIVE_HLS_DIR) / f"live/{key}"
    hls_dir.mkdir(parents=True, exist_ok=True)
    (hls_dir / "index.m3u8").write_text("#EXTM3U\n#EXTINF:2.0,\nseg0.ts\n", encoding="utf-8")

    ok = client.get(
        f"/v1/live/{stream_id}/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    body = ok.json()["data"]
    assert body["stream_id"] == stream_id
    assert body["playlist_present"] is True
    assert body["playlist_age_seconds"] is not None
    assert body["normalize_running"] is False

    denied = client.get(f"/v1/live/{stream_id}/health")
    assert denied.status_code in (401, 403)


def test_check_live_streams_marks_stale(test_user, db_session: Session, monkeypatch, tmp_path):
    import os
    import time

    from src.infrastructure.live.health import check_live_streams

    monkeypatch.setattr(settings, "LIVE_HEALTH_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_STALE_SECONDS", 5)

    token = _auth_token()
    created = _create_stream(token)
    key = created["stream_key"]
    stream_id = created["stream_id"]

    client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}"},
    )
    hls_dir = Path(settings.LIVE_HLS_DIR) / f"live/{key}"
    hls_dir.mkdir(parents=True, exist_ok=True)
    playlist = hls_dir / "index.m3u8"
    playlist.write_text("#EXTM3U\n#EXTINF:2.0,\nseg0.ts\n", encoding="utf-8")
    old = time.time() - 60
    os.utime(playlist, (old, old))

    n = check_live_streams(db_session)
    assert n >= 1

    got = client.get(
        f"/v1/live/{stream_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.json()["data"]["status"] == "idle"


def test_whip_proxy_allows_lab_mediamtx_hosts(monkeypatch):
    from src.application.demo_whip_proxy import whip_proxy_allowed

    monkeypatch.setattr(
        settings, "PUBLIC_WEBRTC_BASE_URL", "http://192.168.1.9:8889"
    )
    assert whip_proxy_allowed("http://192.168.1.9:8889/live/abc12xyz/whip")
    assert whip_proxy_allowed("http://127.0.0.1:8889/live/abc12xyz/whip")
    assert not whip_proxy_allowed("https://evil.example/live/abc12xyz/whip")
    assert not whip_proxy_allowed("http://127.0.0.1:8889/live/abc12xyz/whep")
