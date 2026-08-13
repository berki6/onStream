"""Live archive recorder command flags."""

from src.core.config import settings
from src.infrastructure.media import live_record as lr


def test_archive_ffmpeg_keeps_all_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(lr.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_SEGMENT_SECONDS", 4)
    out = tmp_path / "archive"
    out.mkdir()
    cmd = lr._ffmpeg_cmd("key123", out, copy_audio=True, start_number=7)
    assert cmd[cmd.index("-hls_list_size") + 1] == "0"
    assert cmd[cmd.index("-hls_playlist_type") + 1] == "event"
    assert cmd[cmd.index("-start_number") + 1] == "7"
    flags = cmd[cmd.index("-hls_flags") + 1]
    assert "delete_segments" not in flags
    assert "independent_segments" in flags
    assert "program_date_time" in flags
    assert "append_list" in flags
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert any(str(out / "index.m3u8") == str(x) for x in cmd)


def test_next_segment_index_continues_sequence(tmp_path):
    out = tmp_path / "archive"
    out.mkdir()
    assert lr.next_segment_index(out) == 0
    (out / "seg_00000.ts").write_bytes(b"x")
    (out / "seg_00004.ts").write_bytes(b"x")
    assert lr.next_segment_index(out) == 5


def test_playlist_has_segments_requires_bytes(tmp_path):
    playlist = tmp_path / "index.m3u8"
    playlist.write_text(
        "#EXTM3U\n#EXTINF:2.0,\nseg0.ts\n",
        encoding="utf-8",
    )
    assert lr.playlist_has_segments(playlist) is False
    (tmp_path / "seg0.ts").write_bytes(b"\x00" * 8)
    assert lr.playlist_has_segments(playlist) is True
    assert lr.playlist_media_duration(playlist) == 2.0


def test_stop_record_finalize_is_opt_in_for_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    playlist = (
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n"
        "#EXTINF:2.0,\nseg0.ts\n"
    )
    dest = lr.archive_dir("sidArchive01")
    (dest / "index.m3u8").write_text(playlist, encoding="utf-8")
    lr.stop_record("sidArchive01", finalize=False)
    text = (dest / "index.m3u8").read_text(encoding="utf-8")
    assert "#EXT-X-ENDLIST" not in text
    lr.stop_record("sidArchive01", finalize=True)
    assert "#EXT-X-ENDLIST" in (dest / "index.m3u8").read_text(encoding="utf-8")
