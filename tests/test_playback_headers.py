"""Unit tests for playback CDN cache headers."""

from __future__ import annotations

from src.application.playback_headers import cache_headers
from src.core.config import settings


def test_vod_playlist_short_cache(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=False, asset_name="master.m3u8")
    assert "max-age=3" in h["Cache-Control"]


def test_vod_segment_immutable(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=False, asset_name="720p/segment_001.ts")
    assert "immutable" in h["Cache-Control"]
    assert "31536000" in h["Cache-Control"]


def test_live_playlist_no_cache(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=True, asset_name="index.m3u8")
    assert "no-cache" in h["Cache-Control"]


def test_live_segment_short_cache(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", True)
    h = cache_headers(live=True, asset_name="seg0.ts")
    assert "max-age=2" in h["Cache-Control"]


def test_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "PLAYBACK_CDN_HEADERS_ENABLED", False)
    assert cache_headers(live=False, asset_name="master.m3u8") == {}
    assert cache_headers(live=True, asset_name="seg0.ts") == {}
