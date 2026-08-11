"""Unit tests for playback CDN cache headers."""

from __future__ import annotations

from src.application.playback_headers import cache_headers
from src.core.config import settings


def test_vod_playlist_short_revalidate(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=False, asset_name="master.m3u8")
    assert "max-age=5" in h["Cache-Control"]
    assert "must-revalidate" in h["Cache-Control"]
    assert h["X-Content-Type-Options"] == "nosniff"


def test_vod_segment_immutable(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=False, asset_name="720p/segment_001.ts")
    assert "immutable" in h["Cache-Control"]
    assert "31536000" in h["Cache-Control"]


def test_vod_captions_day_cache(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=False, asset_name="captions.vtt")
    assert "86400" in h["Cache-Control"]


def test_live_playlist_edge_one_second(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=True, asset_name="index.m3u8")
    cc = h["Cache-Control"]
    assert "max-age=0" in cc
    assert "s-maxage=1" in cc
    assert "must-revalidate" in cc
    assert "no-store" not in cc


def test_live_segment_short_cache(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=True, asset_name="seg0.ts")
    assert "max-age=4" in h["Cache-Control"]


def test_live_captions_no_store(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=True, asset_name="captions.vtt")
    assert h["Cache-Control"] == "no-store"


def test_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", False)
    assert cache_headers(live=False, asset_name="master.m3u8") == {}
    assert cache_headers(live=True, asset_name="seg0.ts") == {}
