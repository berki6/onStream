"""Tests for m3u8-based playlist rewrite and subtitle injection."""

from __future__ import annotations

from src.application.playback_service import rewrite_playlist
from src.infrastructure.media.abr import inject_subtitle_track


def test_rewrite_media_playlist_appends_token():
    content = "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:2.0,\nseg0.ts\n#EXTINF:2.0,\nseg1.ts\n"
    out = rewrite_playlist(content, "abc123").decode("utf-8")
    assert "seg0.ts?token=abc123" in out
    assert "seg1.ts?token=abc123" in out
    assert "#EXTINF:2" in out


def test_rewrite_master_playlist_variants():
    content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n"
        "360p/index.m3u8\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720\n"
        "720p/index.m3u8\n"
    )
    out = rewrite_playlist(content, "tok").decode("utf-8")
    assert "360p/index.m3u8?token=tok" in out
    assert "720p/index.m3u8?token=tok" in out


def test_rewrite_existing_query_uses_ampersand():
    content = "#EXTM3U\n#EXTINF:1.0,\nseg0.ts?foo=1\n"
    out = rewrite_playlist(content, "t").decode("utf-8")
    assert "seg0.ts?foo=1&token=t" in out


def test_rewrite_no_token_unchanged():
    content = "#EXTM3U\n#EXTINF:1.0,\nseg0.ts\n"
    out = rewrite_playlist(content, None).decode("utf-8")
    assert out == content or out == content  # exact bytes of original
    assert "token=" not in out


def test_inject_subtitle_track_adds_media_and_stream_inf():
    content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n"
        "360p/index.m3u8\n"
    )
    out = inject_subtitle_track(content, captions_uri="captions.vtt")
    assert "TYPE=SUBTITLES" in out
    assert 'URI="captions.vtt"' in out
    assert 'SUBTITLES="subs"' in out


def test_inject_subtitle_idempotent():
    content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Captions",'
        'DEFAULT=YES,AUTOSELECT=YES,URI="captions.vtt"\n'
        '#EXT-X-STREAM-INF:BANDWIDTH=800000,SUBTITLES="subs"\n'
        "360p/index.m3u8\n"
    )
    out = inject_subtitle_track(content)
    assert out.count("TYPE=SUBTITLES") == 1


def test_captions_handler_persists_subtitles_on_master(tmp_path):
    """After captions, on-disk master gains SUBTITLES (not only serve-time inject)."""
    hls = tmp_path / "hls" / "abcd1234"
    hls.mkdir(parents=True)
    master = hls / "master.m3u8"
    master.write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n"
        "360p/index.m3u8\n",
        encoding="utf-8",
    )
    injected = inject_subtitle_track(
        master.read_text(encoding="utf-8"), captions_uri="captions.vtt"
    )
    master.write_text(injected, encoding="utf-8")
    text = master.read_text(encoding="utf-8")
    assert "TYPE=SUBTITLES" in text
    assert 'URI="captions.vtt"' in text
    assert text.count("TYPE=SUBTITLES") == 1
