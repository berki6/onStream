"""LL-HLS playlist wait, URI rewrite, and live master resolution."""

from __future__ import annotations

from types import SimpleNamespace

from src.application import live_service, ll_hls, playback_service
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings


SAMPLE = """#EXTM3U
#EXT-X-VERSION:6
#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK=1.000
#EXT-X-MEDIA-SEQUENCE:10
#EXT-X-PART:DURATION=0.333,URI="seg_00010.m4s",INDEPENDENT=YES
#EXTINF:1.000,
seg_00010.m4s
#EXT-X-PART:DURATION=0.333,URI="seg_00011.m4s",INDEPENDENT=YES
#EXT-X-PRELOAD-HINT:TYPE=PART,URI="seg_00011.m4s"
"""


def test_latest_msn_part_and_has_reached():
    msn, part = ll_hls.latest_msn_part(SAMPLE)
    assert msn == 11
    assert part == 0
    assert ll_hls.has_reached(SAMPLE, 11, 0) is True
    assert ll_hls.has_reached(SAMPLE, 12, 0) is False
    assert ll_hls.is_ll_playlist(SAMPLE) is True


def test_wait_for_playlist_blocks_until_msn(tmp_path):
    path = tmp_path / "index.m3u8"
    path.write_text(SAMPLE)
    text = ll_hls.wait_for_playlist(path, msn=11, part=0, timeout=0.2)
    assert "EXT-X-PART" in text
    early = (
        "#EXTM3U\n#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES\n"
        "#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PART:DURATION=0.3,URI=\"p.m4s\"\n"
    )
    path.write_text(early)
    stalled = ll_hls.wait_for_playlist(path, msn=9, part=0, timeout=0.15)
    assert "MEDIA-SEQUENCE:0" in stalled


def test_wait_for_playlist_does_not_block_dvr(tmp_path):
    path = tmp_path / "index.m3u8"
    dvr = "#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:4,\nseg.ts\n"
    path.write_text(dvr)
    text = ll_hls.wait_for_playlist(path, msn=99, part=0, timeout=2.0)
    assert text == dvr


def test_append_token_to_quoted_uris():
    out = ll_hls.append_token_to_quoted_uris(SAMPLE, "abc")
    assert 'URI="seg_00010.m4s?token=abc"' in out
    assert 'URI="seg_00011.m4s?token=abc"' in out
    again = ll_hls.append_token_to_quoted_uris(out, "abc")
    assert again.count("token=abc") == out.count("token=abc")


def test_rewrite_playlist_tokenizes_part_uris():
    out = playback_service.rewrite_playlist(SAMPLE, "tok").decode("utf-8")
    assert 'URI="seg_00010.m4s?token=tok"' in out
    assert "seg_00010.m4s?token=tok" in out


def test_inject_live_edge_skips_part_playlists():
    out = playback_service.inject_live_edge_start(SAMPLE)
    assert "#EXT-X-START" not in out


def test_resolve_master_ll_skips_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", True)
    stream_id = "llStream01ab"
    arch = tmp_path / stream_id / "archive"
    arch.mkdir(parents=True)
    (arch / "seg.ts").write_bytes(b"ts")
    (arch / "index.m3u8").write_text("#EXTM3U\n# archive EVENT\n#EXTINF:4,\nseg.ts\n")
    ll = tmp_path / stream_id / "ll"
    ll.mkdir(parents=True)
    (ll / "index.m3u8").write_text("#EXTM3U\n#EXT-X-PART:DURATION=0.3,URI=\"p.m4s\"\n")
    stream = SimpleNamespace(
        stream_id=stream_id,
        hls_path="live/somekey",
        abr_hls_path=None,
    )
    dvr = live_service.resolve_master(stream)
    assert dvr.parent.name == "archive"
    got = live_service.resolve_master(stream, latency="ll")
    assert got == ll / "index.m3u8"
    assert "EXT-X-PART" in got.read_text()


def test_resolve_master_ll_404_without_ll_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_HLS_DIR", tmp_path)
    monkeypatch.setattr(settings, "LIVE_ABR_ENABLED", False)
    monkeypatch.setattr(settings, "LIVE_ARCHIVE_ENABLED", True)
    stream_id = "llMissing01"
    arch = tmp_path / stream_id / "archive"
    arch.mkdir(parents=True)
    (arch / "index.m3u8").write_text("#EXTM3U\n# archive\n")
    stream = SimpleNamespace(
        stream_id=stream_id,
        hls_path=None,
        abr_hls_path=None,
    )
    try:
        live_service.resolve_master(stream, latency="ll")
        assert False, "expected missing LL playlist"
    except AppError as exc:
        assert exc.code == ErrorCode.LIVE_NOT_FOUND
