"""Live ingest normalize (WHIP VP8/Opus → H.264/AAC HLS)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.config import settings
from src.infrastructure.media import live_normalize as ln


def test_tracks_need_transcode_vp8_opus():
    assert ln.tracks_need_transcode(["Opus", "VP8"]) is True
    classified = ln.classify_tracks(["Opus", "VP8"])
    assert classified["video_copy"] is False
    assert classified["audio_copy"] is False


def test_tracks_passthrough_h264_aac():
    assert ln.tracks_need_transcode(["H264", "MPEG-4 Audio"]) is False
    classified = ln.classify_tracks(["H264", "MPEG-4 Audio"])
    assert classified["video_copy"] is True
    assert classified["audio_copy"] is True


def test_tracks_copy_video_transcode_opus():
    classified = ln.classify_tracks(["H264", "Opus"])
    assert classified["needs_transcode"] is True
    assert classified["video_copy"] is True
    assert classified["audio_copy"] is False


def test_extract_track_names_from_dicts():
    names = ln.extract_track_names(
        {"tracks": [{"codec": "VP8"}, {"codecName": "Opus"}]}
    )
    assert names == ["VP8", "Opus"]


def test_start_normalize_spawns_ffmpeg_for_webrtc_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554")

    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    path_info = {
        "ready": True,
        "tracks": ["Opus", "VP8"],
        "source": {"type": "webRTCSession", "id": "s1"},
    }

    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.shutil, "which", return_value="ffmpeg"):
            with patch.object(ln.subprocess, "Popen", return_value=fake_proc) as popen:
                stop = ln.threading.Event()
                ln._probe_and_run("abc12xyzABXY", "streamKey1234567890abcd", stop)
                popen.assert_called_once()
                cmd = popen.call_args[0][0]
                assert "libx264" in cmd
                assert "aac" in cmd
                assert cmd[cmd.index("-hls_time") + 1] == "1"
                assert "-tune" in cmd and "zerolatency" in cmd
                assert any("rtsp://127.0.0.1:8554/live/" in str(x) for x in cmd)

    ln.stop_normalize("abc12xyzABXY")


def test_webrtc_without_tracks_still_spawns(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    path_info = {"tracks": [], "source": {"type": "webRTCSession"}}
    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.shutil, "which", return_value="ffmpeg"):
            with patch.object(ln.subprocess, "Popen", return_value=fake_proc) as popen:
                stop = ln.threading.Event()
                ln._probe_and_run("webRtcNoTrk1", "whipKey", stop)
                popen.assert_called_once()
    ln.stop_normalize("webRtcNoTrk1")


def test_short_live_segments_reencode_h264_for_idrs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_SEGMENT_SECONDS", 1)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554")
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    path_info = {
        "tracks": ["H264", "Opus"],
        "source": {"type": "webRTCSession"},
    }
    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.shutil, "which", return_value="ffmpeg"):
            with patch.object(ln.subprocess, "Popen", return_value=fake_proc) as popen:
                stop = ln.threading.Event()
                ln._probe_and_run("h264OpusSeg1", "whipKey2", stop)
                cmd = popen.call_args[0][0]
                assert "libx264" in cmd
                assert cmd[cmd.index("-c:v") + 1] != "copy"
                assert cmd[cmd.index("-g") + 1] == "30"
    ln.stop_normalize("h264OpusSeg1")


def test_passthrough_does_not_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    path_info = {"tracks": ["H264", "MPEG-4 Audio"], "source": {"type": "rtmpConn"}}
    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.subprocess, "Popen") as popen:
            stop = ln.threading.Event()
            ln._probe_and_run("idPassthrough1", "obsKey", stop)
            popen.assert_not_called()


def test_resolve_master_prefers_normalized_hls(tmp_path, monkeypatch):
    from src.application import live_service
    from types import SimpleNamespace

    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    stream_id = "normStream01"
    mtx_dir = tmp_path / "live" / "somekey"
    mtx_dir.mkdir(parents=True)
    (mtx_dir / "index.m3u8").write_text("#EXTM3U\n# MTX crashed leftover\n")
    norm_dir = tmp_path / stream_id
    norm_dir.mkdir()
    (norm_dir / "index.m3u8").write_text("#EXTM3U\n# normalized\n")
    stream = SimpleNamespace(
        stream_id=stream_id,
        hls_path="live/somekey",
        abr_hls_path=None,
    )
    got = live_service.resolve_master(stream)
    assert got == norm_dir / "index.m3u8"
    assert "normalized" in got.read_text()


def test_passthrough_still_spawns_ll(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554")
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    path_info = {"tracks": ["H264", "MPEG-4 Audio"], "source": {"type": "rtmpConn"}}
    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.shutil, "which", return_value="ffmpeg"):
            with patch.object(ln.subprocess, "Popen", return_value=fake_proc) as popen:
                stop = ln.threading.Event()
                ln._probe_and_run("idPassLlHls1", "obsKey", stop)
                popen.assert_called_once()
                cmd = popen.call_args[0][0]
                assert "-hls_part_size" in cmd
                assert "fmp4" in cmd
    ln.stop_normalize("idPassLlHls1")


def test_webrtc_with_ll_spawns_both(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_LL_HLS_ENABLED", True)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.0)
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554")
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    path_info = {
        "ready": True,
        "tracks": ["Opus", "VP8"],
        "source": {"type": "webRTCSession", "id": "s1"},
    }
    with patch.object(ln.mediamtx_client, "get_path", return_value=path_info):
        with patch.object(ln.shutil, "which", return_value="ffmpeg"):
            with patch.object(ln.subprocess, "Popen", return_value=fake_proc) as popen:
                stop = ln.threading.Event()
                ln._probe_and_run("webRtcLlBoth", "whipKeyLl", stop)
                assert popen.call_count == 2
                cmds = [c[0][0] for c in popen.call_args_list]
                assert any("-hls_part_size" in cmd for cmd in cmds)
                assert any("-hls_part_size" not in cmd for cmd in cmds)
    ln.stop_normalize("webRtcLlBoth")
