"""Unit tests for MediaMTX control client kick/get helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.infrastructure.live import mediamtx_client as mtx


def test_encode_path_name_encodes_slash():
    assert mtx._encode_path_name("live/abcKey") == "live%2FabcKey"


def test_kick_publisher_rtmp_uses_connection_id():
    path_info = {
        "name": "live/abcKey",
        "ready": True,
        "source": {"type": "rtmpConn", "id": "conn-42"},
    }
    get_resp = MagicMock(status_code=200)
    get_resp.json.return_value = path_info
    kick_resp = MagicMock(status_code=200)

    with patch.object(mtx, "_base_url", return_value="http://127.0.0.1:9997"):
        with patch.object(mtx, "_get", return_value=get_resp) as get_mock:
            with patch.object(mtx, "_post", return_value=kick_resp) as post_mock:
                assert mtx.kick_publisher("live/abcKey") is True

    get_mock.assert_called_once_with("/v3/paths/get/live%2FabcKey")
    post_mock.assert_called_once_with("/v3/rtmpconns/kick/conn-42")


def test_kick_publisher_webrtc_maps_segment():
    path_info = {
        "source": {"type": "webRTCSession", "id": "whep-1"},
    }
    get_resp = MagicMock(status_code=200)
    get_resp.json.return_value = path_info
    kick_resp = MagicMock(status_code=200)

    with patch.object(mtx, "_base_url", return_value="http://127.0.0.1:9997"):
        with patch.object(mtx, "_get", return_value=get_resp):
            with patch.object(mtx, "_post", return_value=kick_resp) as post_mock:
                assert mtx.kick_publisher("live/key") is True

    post_mock.assert_called_once_with("/v3/webrtcsessions/kick/whep-1")


def test_kick_publisher_missing_path_returns_false():
    get_resp = MagicMock(status_code=404)
    with patch.object(mtx, "_base_url", return_value="http://127.0.0.1:9997"):
        with patch.object(mtx, "_get", return_value=get_resp):
            with patch.object(mtx, "_post") as post_mock:
                assert mtx.kick_publisher("live/gone") is False
                post_mock.assert_not_called()


def test_kick_publisher_no_api_url():
    with patch.object(mtx, "_base_url", return_value=""):
        assert mtx.kick_publisher("live/x") is False
