"""Lab HTTPS edge: Caddyfile contracts, env rewrite, WHIP allowlist, webrtc base."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from src.core.config import settings

ROOT = Path(__file__).resolve().parents[1]


def _load_sync_lan_ip():
    spec = importlib.util.spec_from_file_location(
        "onstream_sync_lan_ip", ROOT / "scripts" / "sync_lan_ip.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_caddyfile_is_real_tls_edge():
    text = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "auto_https off" in text
    assert ":443" in text
    assert "tls /certs/lab.pem /certs/lab-key.pem" in text
    assert "handle /lab/ca.crt" in text
    assert "handle /live/*" in text
    assert "handle_path /live" not in text
    assert "ONSTREAM_EDGE_WEBRTC" in text
    assert "ONSTREAM_EDGE_API" in text
    assert "reverse_proxy" in text
    assert "8189/udp" not in text
    assert ":8189" not in text.split("handle /live/*")[1]


def test_caddyfile_host_is_native_loopback_edge():
    text = (ROOT / "deploy" / "Caddyfile.host").read_text(encoding="utf-8")
    assert "tls ./certs/lab.pem ./certs/lab-key.pem" in text
    assert "handle /lab/ca.crt" in text
    assert "handle /live/*" in text
    assert "handle_path /live" not in text
    assert "reverse_proxy 127.0.0.1:8889" in text
    assert "reverse_proxy 127.0.0.1:8000" in text
    assert "header_down Location ^https?://[^/]+(?::8889)?" in text
    assert "host.docker.internal" not in text
    assert "mediamtx:8889" not in text


def test_rewrite_https_keeps_expo_on_http_api():
    sync = _load_sync_lan_ip()
    raw = (
        "PUBLIC_API_BASE_URL=http://localhost:8000\n"
        "PUBLIC_WEBRTC_BASE_URL=http://localhost:8889\n"
        "PUBLIC_HTTPS_BASE_URL=\n"
        "EXPO_PUBLIC_API_BASE_URL=http://localhost:8000\n"
    )
    out = sync.rewrite_https(raw, "192.168.1.9", include_webrtc=True)
    assert "PUBLIC_API_BASE_URL=http://192.168.1.9:8000" in out
    assert "EXPO_PUBLIC_API_BASE_URL=http://192.168.1.9:8000" in out
    assert "PUBLIC_WEBRTC_BASE_URL=https://192.168.1.9" in out
    assert "PUBLIC_HTTPS_BASE_URL=https://192.168.1.9" in out
    assert "ONSTREAM_LAN_IP=192.168.1.9" in out
    webrtc_line = [
        line
        for line in out.splitlines()
        if line.startswith("PUBLIC_WEBRTC_BASE_URL=")
    ][0]
    assert webrtc_line == "PUBLIC_WEBRTC_BASE_URL=https://192.168.1.9"


def test_rewrite_http_does_not_touch_https_keys():
    sync = _load_sync_lan_ip()
    raw = (
        "PUBLIC_API_BASE_URL=http://192.168.1.3:8000\n"
        "PUBLIC_WEBRTC_BASE_URL=http://192.168.1.3:8889\n"
    )
    out = sync.rewrite(raw, "192.168.1.9")
    assert "PUBLIC_API_BASE_URL=http://192.168.1.9:8000" in out
    assert "PUBLIC_WEBRTC_BASE_URL=http://192.168.1.9:8889" in out
    assert "PUBLIC_HTTPS_BASE_URL" not in out


def test_rewrite_does_not_mangle_api_port_into_webrtc():
    sync = _load_sync_lan_ip()
    raw = "PUBLIC_API_BASE_URL=http://192.168.1.3:8000\n"
    out = sync.rewrite(raw, "192.168.1.9")
    assert out == "PUBLIC_API_BASE_URL=http://192.168.1.9:8000\n"


def test_whip_proxy_allows_https_edge_and_loopback(monkeypatch):
    from src.application.demo_whip_proxy import whip_proxy_allowed

    monkeypatch.setattr(settings, "PUBLIC_WEBRTC_BASE_URL", "https://192.168.1.9")
    monkeypatch.setattr(settings, "PUBLIC_HTTPS_BASE_URL", "https://192.168.1.9")
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "http://192.168.1.9:8000")
    assert whip_proxy_allowed("https://192.168.1.9/live/abc12xyz/whip")
    assert whip_proxy_allowed("http://127.0.0.1:8889/live/abc12xyz/whip")
    assert not whip_proxy_allowed("https://evil.example/live/abc12xyz/whip")
    assert not whip_proxy_allowed("http://192.168.1.9:8000/live/abc12xyz/whip")
    assert not whip_proxy_allowed("https://192.168.1.9/live/abc12xyz/whep")


def test_webrtc_base_prefers_https_origin(monkeypatch):
    from src.application.live_service import _webrtc_base

    monkeypatch.setattr(settings, "PUBLIC_WEBRTC_BASE_URL", "http://192.168.1.9:8889")
    monkeypatch.setattr(settings, "PUBLIC_HTTPS_BASE_URL", "https://192.168.1.9")
    assert _webrtc_base() == "https://192.168.1.9"
    monkeypatch.setattr(settings, "PUBLIC_HTTPS_BASE_URL", "")
    assert _webrtc_base() == "http://192.168.1.9:8889"
