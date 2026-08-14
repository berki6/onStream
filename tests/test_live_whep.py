"""Tokenized live WHEP gateway tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.application import live_whep as live_whep_mod
from src.core.config import settings
from src.infrastructure.db.session import get_db
from src.main import app
from tests.conftest import override_get_db
from tests.test_live_streams import _auth_token, _create_stream

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

OFFER = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
ANSWER = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=answer\r\nt=0 0\r\n"


@pytest.fixture(autouse=True)
def _live_whep_defaults(monkeypatch):
    monkeypatch.setattr(settings, "LIVE_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(settings, "PUBLIC_WEBRTC_BASE_URL", "http://192.168.1.6:8889")
    monkeypatch.setattr(settings, "MEDIAMTX_WEBRTC_URL", "http://127.0.0.1:8889")
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", False)


def _publish(token: str, is_public: bool = False) -> dict:
    created = _create_stream(token, is_public=is_public)
    key = created["stream_key"]
    client.post(
        "/v1/live/mediamtx-auth",
        json={"action": "publish", "path": f"live/{key}"},
    )
    return created


def _mtx_base() -> str:
    return (settings.MEDIAMTX_WEBRTC_URL or "http://127.0.0.1:8889").rstrip("/")


def _mtx_response(location: str | None = None):
    if location is None:
        location = f"{_mtx_base()}/live/k/whep/s/abc"
    res = MagicMock()
    res.status_code = 201
    res.text = ANSWER
    res.headers = {"Location": location}
    return res


def test_token_includes_whep_playback_url(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token)
    tok = client.post(
        f"/v1/live/{created['stream_id']}/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert tok.status_code == 200
    data = tok.json()["data"]
    assert data["token"]
    assert f"/v1/playback/live/{created['stream_id']}/whep?token=" in data[
        "whep_playback_url"
    ]
    assert created["stream_key"] not in data["whep_playback_url"]
    assert created["whep_url"] != data["whep_playback_url"]
    assert data.get("ll_playback_url") in (None, "")


def test_whep_private_requires_token(test_user, db_session: Session):
    token = _auth_token()
    created = _publish(token, is_public=False)
    denied = client.post(
        f"/v1/playback/live/{created['stream_id']}/whep",
        content=OFFER,
        headers={"Content-Type": "application/sdp"},
    )
    assert denied.status_code == 401


def test_whep_not_live_returns_404(test_user, db_session: Session):
    token = _auth_token()
    created = _create_stream(token, is_public=True)
    resp = client.post(
        f"/v1/playback/live/{created['stream_id']}/whep",
        content=OFFER,
        headers={"Content-Type": "application/sdp"},
    )
    assert resp.status_code == 404


def test_whep_offer_stores_opaque_session(test_user, db_session: Session):
    token = _auth_token()
    created = _publish(token, is_public=False)
    key = created["stream_key"]
    stream_id = created["stream_id"]
    tok = client.post(
        f"/v1/live/{stream_id}/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    ).json()["data"]["token"]

    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        return_value=_mtx_response(
            f"http://evil.example/live/{key}/whep/s/sess1"
        )
    )
    fake_client.delete = AsyncMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
    fake_cm.__aexit__ = AsyncMock(return_value=False)

    store = {}

    def _setex(k, _ttl, v):
        store[k] = v
        return True

    def _get(k):
        return store.get(k)

    with patch("src.application.live_whep.httpx.AsyncClient", return_value=fake_cm):
        with patch("src.application.live_whep.redis_client") as redis_mod:
            redis_mod.setex.side_effect = _setex
            redis_mod.get.side_effect = _get
            redis_mod.delete.side_effect = lambda k: store.pop(k, None)
            ok = client.post(
                f"/v1/playback/live/{stream_id}/whep?token={tok}&target=http://evil.example/whip",
                content=OFFER,
                headers={"Content-Type": "application/sdp"},
            )
            assert ok.status_code == 201
            assert ok.text == ANSWER
            loc = ok.headers.get("location") or ok.headers.get("Location")
            assert loc
            assert f"/v1/playback/live/{stream_id}/whep/sessions/" in loc
            assert key not in loc
            assert "evil.example" not in loc
            assert any(
                k.startswith(f"whep:{stream_id}:")
                and f"{_mtx_base()}/live/{key}/whep/s/sess1" == v
                for k, v in store.items()
            )
            assert all("evil.example" not in v for v in store.values())
            posted = fake_client.post.call_args
            assert posted[0][0] == f"{_mtx_base()}/live/{key}/whep"
            assert "192.168.1.6" not in posted[0][0]
            assert posted[1]["headers"]["Content-Type"] == "application/sdp"
            body = posted[1]["content"]
            assert body.startswith(b"v=")
            assert body.endswith(b"\n")

            session_id = loc.split("/sessions/")[-1].split("?")[0]
            stopped = client.delete(
                f"/v1/playback/live/{stream_id}/whep/sessions/{session_id}?token={tok}"
            )
            assert stopped.status_code == 204
            fake_client.delete.assert_called_once()
            assert key in fake_client.delete.call_args[0][0]


def test_whep_sdp_too_large(test_user, db_session: Session):
    token = _auth_token()
    created = _publish(token, is_public=True)
    huge = "v=0\n" + ("a" * live_whep_mod.MAX_SDP_BYTES)
    resp = client.post(
        f"/v1/playback/live/{created['stream_id']}/whep",
        content=huge,
        headers={"Content-Type": "application/sdp"},
    )
    assert resp.status_code == 400


def test_whep_delete_unknown_session(test_user, db_session: Session):
    token = _auth_token()
    created = _publish(token, is_public=True)
    with patch("src.application.live_whep.redis_client") as redis_mod:
        redis_mod.get.return_value = None
        missing = client.delete(
            f"/v1/playback/live/{created['stream_id']}/whep/sessions/aaaaaaaaaaaaaaaa"
        )
        assert missing.status_code == 404
