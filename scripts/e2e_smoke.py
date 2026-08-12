"""Local end-to-end smoke against a running OnStream stack (API + worker + MediaMTX).

Usage (from repo root, with services up):
  .\\.venv\\Scripts\\python.exe scripts/e2e_smoke.py
"""
from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
LAN_HINT = "192.168.1.2"
SAMPLE = Path("data/e2e-sample.mp4")


def request(
    method: str,
    path: str,
    *,
    data: dict | None = None,
    headers: dict | None = None,
    files: dict | None = None,
    form_fields: dict | None = None,
    expect_json: bool = True,
):
    url = BASE + path
    h = dict(headers or {})
    body = None
    if files:
        boundary = "----onstream" + uuid.uuid4().hex
        parts: list[bytes] = []
        for name, (fname, content, ctype) in files.items():
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{fname}"\r\n'
                    f"Content-Type: {ctype}\r\n\r\n"
                ).encode()
            )
            parts.append(content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif form_fields is not None:
        from urllib.parse import urlencode

        body = urlencode(form_fields).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    h.setdefault("Accept", "application/json" if expect_json else "*/*")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            if not expect_json:
                return resp.status, raw
            text = raw.decode() if raw else ""
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        if not expect_json:
            return e.code, raw
        text = raw.decode() if raw else ""
        try:
            return e.code, json.loads(text) if text else {}
        except json.JSONDecodeError:
            return e.code, {"raw": text}


def ok(name: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise SystemExit(1)


def main() -> None:
    if not SAMPLE.exists():
        raise SystemExit(f"Missing {SAMPLE}; generate with ffmpeg first")

    suffix = uuid.uuid4().hex[:10]
    email = f"e2e_{suffix}@test.local"
    username = f"e2e_{suffix}"
    password = "E2eTestPass123!"

    st, body = request("GET", "/health")
    ok("health", st == 200, f"status={st}")

    st, raw = request("GET", "/demo/", expect_json=False)
    ok(
        "demo player mounted",
        st == 200 and b"hls" in raw.lower()[:8000],
        f"status={st}",
    )

    st, body = request(
        "POST",
        "/v1/auth/register",
        data={"email": email, "username": username, "password": password},
    )
    ok("register", st in (200, 201), f"status={st} body={body}")

    st, body = request(
        "POST",
        "/v1/auth/login",
        data=None,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        form_fields={"username": username, "password": password},
    )
    ok("login", st == 200 and body.get("success") is not False, f"status={st}")
    data = body.get("data") or body
    token = data.get("access_token") or (data.get("tokens") or {}).get(
        "access_token"
    )
    ok("access token", bool(token), str(list(data.keys()) if isinstance(data, dict) else data)[:200])
    auth = {"Authorization": f"Bearer {token}"}

    content = SAMPLE.read_bytes()
    st, body = request(
        "POST",
        "/v1/videos/",
        headers=auth,
        files={"file": (SAMPLE.name, content, "video/mp4")},
    )
    ok("vod upload", st in (200, 201), f"status={st} body={str(body)[:300]}")
    vdata = body.get("data") or body
    video_id = vdata.get("id") or vdata.get("upload_id") or vdata.get("video_id")
    ok("video id", bool(video_id), str(vdata)[:200])

    ready = False
    last = None
    for _ in range(90):
        st, body = request("GET", f"/v1/videos/{video_id}", headers=auth)
        last = body
        status = ((body.get("data") or body).get("status") or "").upper()
        if status in ("READY", "COMPLETED", "DONE"):
            ready = True
            break
        if status in ("ERROR", "FAILED"):
            break
        time.sleep(2)
    ok("vod READY", ready, f"last={str(last)[:400]}")

    st, body = request(
        "POST",
        f"/v1/videos/{video_id}/tokens",
        data={"type": "playback"},
        headers=auth,
    )
    ok("vod token", st == 200, f"status={st} body={str(body)[:300]}")
    pdata = body.get("data") or body
    playback_url = pdata.get("playback_url") or pdata.get("url")
    ok(
        "playback_url uses LAN base",
        bool(playback_url) and LAN_HINT in (playback_url or ""),
        playback_url or "",
    )

    req = urllib.request.Request(playback_url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        playlist = resp.read().decode()
    ok("vod master.m3u8", "#EXTM3U" in playlist, playlist[:120].replace("\n", " "))

    st, body = request(
        "POST",
        "/v1/live/",
        data={"title": "e2e live"},
        headers=auth,
    )
    if st >= 400:
        st, body = request("POST", "/v1/live/", data={}, headers=auth)
    ok("live create", st in (200, 201), f"status={st} body={str(body)[:400]}")
    ldata = body.get("data") or body
    stream_id = ldata.get("id") or ldata.get("stream_id")
    stream_key = ldata.get("stream_key")
    rtmp = ldata.get("rtmp_url") or ldata.get("rtmp")
    ok(
        "live stream_id + key",
        bool(stream_id) and bool(stream_key),
        f"id={stream_id} rtmp={rtmp}",
    )

    st, body = request("GET", f"/v1/live/{stream_id}/health", headers=auth)
    ok("live health endpoint", st == 200, f"status={st} body={str(body)[:250]}")

    st, body = request(
        "POST",
        f"/v1/live/{stream_id}/tokens",
        data={"type": "playback"},
        headers=auth,
    )
    ok("live token", st == 200, f"status={st} body={str(body)[:300]}")

    try:
        with urllib.request.urlopen("http://127.0.0.1:9997/v3/paths/list", timeout=5) as resp:
            ok("mediamtx api", resp.status == 200, "paths/list ok")
    except Exception as e:
        ok("mediamtx api", False, str(e))

    st, body = request("DELETE", f"/v1/live/{stream_id}", headers=auth)
    ok("live revoke", st in (200, 204), f"status={st}")

    print("\nAll API e2e checks passed.")
    print(f"Expo API base: http://{LAN_HINT}:8000 (onstream-demo/.env)")
    print("For OBS: create a new live stream in Expo (this smoke revoked its stream).")


if __name__ == "__main__":
    main()
