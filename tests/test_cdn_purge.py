"""CDN purge unit tests (httpx mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import settings
from src.infrastructure.cdn import get_cdn_purger, reset_cdn_purger
from src.infrastructure.cdn.bunny import BunnyCdnPurger
from src.infrastructure.cdn.cloudflare import CloudflareCdnPurger
from src.infrastructure.cdn.noop import NoopCdnPurger


@pytest.fixture(autouse=True)
def _reset_purger():
    reset_cdn_purger()
    yield
    reset_cdn_purger()


def test_noop_purger_does_not_raise():
    NoopCdnPurger().purge_urls(["http://example.com/a.m3u8"])


def test_factory_defaults_to_noop(monkeypatch):
    monkeypatch.setattr(settings, "CDN_PROVIDER", "none")
    assert isinstance(get_cdn_purger(), NoopCdnPurger)


def test_cloudflare_purge_posts_files(monkeypatch):
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setattr(settings, "CLOUDFLARE_ZONE_ID", "zone123")
    purger = CloudflareCdnPurger()

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"success": True}

    with patch("src.infrastructure.cdn.cloudflare.httpx.Client") as Client:
        client = Client.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        purger.purge_urls(["https://cdn.example/v1/playback/abc/master.m3u8"])

    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert "zones/zone123/purge_cache" in args[0]
    assert kwargs["json"]["files"] == [
        "https://cdn.example/v1/playback/abc/master.m3u8"
    ]
    assert "Bearer tok" in kwargs["headers"]["Authorization"]


def test_bunny_purge_posts_url(monkeypatch):
    monkeypatch.setattr(settings, "BUNNY_API_KEY", "bunnykey")
    purger = BunnyCdnPurger()

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("src.infrastructure.cdn.bunny.httpx.Client") as Client:
        client = Client.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        purger.purge_urls(["https://cdn.example/master.m3u8"])

    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert "api.bunny.net/purge" in args[0]
    assert kwargs["headers"]["AccessKey"] == "bunnykey"
