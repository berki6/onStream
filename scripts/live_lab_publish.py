"""Live lab publisher: loop a sample MP4 to RTMP and print phone checklist.

Does **not** start API / worker / MediaMTX / Expo — those stay in their own terminals.

Usage (from repo root, with API + worker + MediaMTX already up):

  # A) You already created a stream in Expo — paste the plaintext key:
  .\\.venv\\Scripts\\python.exe scripts/live_lab_publish.py --stream-key YOUR_KEY

  # B) Script creates a stream (login), then publishes:
  .\\.venv\\Scripts\\python.exe scripts/live_lab_publish.py --username demo --password YourPassword

  # Optional env: ONSTREAM_LAB_BASE, ONSTREAM_LAB_USER, ONSTREAM_LAB_PASSWORD,
  #               ONSTREAM_LAB_RTMP, ONSTREAM_LAB_MEDIAMTX_API

Ctrl+C stops FFmpeg. Mode B revokes the stream on exit by default.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = ROOT / "tests" / "media" / "test-video.mp4"
DEFAULT_BASE = os.environ.get("ONSTREAM_LAB_BASE", "http://127.0.0.1:8000")
DEFAULT_RTMP = os.environ.get("ONSTREAM_LAB_RTMP", "rtmp://127.0.0.1:1935/live")
DEFAULT_MTX = os.environ.get("ONSTREAM_LAB_MEDIAMTX_API", "http://127.0.0.1:9997")


def api(
    method: str,
    base: str,
    path: str,
    *,
    data: dict | None = None,
    form_fields: dict | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict]:
    url = base.rstrip("/") + path
    headers: dict[str, str] = {"Accept": "application/json"}
    body: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form_fields is not None:
        body = urlencode(form_fields).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            payload = {"raw": text}
        raise SystemExit(f"HTTP {e.code} {method} {path}: {payload}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"API unreachable ({url}): {e}") from e


def login(base: str, username: str, password: str) -> str:
    st, body = api(
        "POST",
        base,
        "/v1/auth/login",
        form_fields={"username": username, "password": password},
    )
    if st != 200:
        raise SystemExit(f"Login failed: {body}")
    data = body.get("data") or body
    token = data.get("access_token") or (data.get("tokens") or {}).get("access_token")
    if not token:
        raise SystemExit(f"No access_token in login response: {body}")
    return token


def create_stream(base: str, token: str, title: str) -> dict:
    st, body = api(
        "POST",
        base,
        "/v1/live/",
        data={"title": title, "is_public": False},
        token=token,
    )
    if st not in (200, 201):
        raise SystemExit(f"Create live failed: {body}")
    data = body.get("data") or body
    if not data.get("stream_key"):
        raise SystemExit(f"No stream_key in create response (shown once): {body}")
    return data


def revoke_stream(base: str, token: str, stream_id: str) -> None:
    st, body = api("DELETE", base, f"/v1/live/{stream_id}", token=token)
    if st != 200:
        print(f"[warn] revoke failed HTTP {st}: {body}")
    else:
        print(f"[ok] revoked stream {stream_id}")


def wait_path_online(mtx_api: str, path_name: str, timeout_s: float = 25.0) -> bool:
    encoded = quote(path_name.strip("/"), safe="")
    url = f"{mtx_api.rstrip('/')}/v3/paths/get/{encoded}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    info = json.loads(resp.read().decode())
                    source = info.get("source") or {}
                    if source.get("id") or info.get("ready"):
                        return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def print_banner(
    stream_id: str | None, stream_key: str, rtmp_url: str, video: Path
) -> None:
    print()
    print("=" * 60)
    print("  OnStream live lab publisher")
    print("=" * 60)
    if stream_id:
        print(f"  stream_id : {stream_id}")
    print(f"  stream_key: {stream_key[:8]}… ({len(stream_key)} chars)")
    print(f"  rtmp      : {rtmp_url}")
    print(f"  source    : {video}")
    print("=" * 60)
    print()


def print_phone_checklist(stream_id: str | None) -> None:
    if stream_id:
        same = (
            f"Open the **live stream detail** for `{stream_id}` "
            "(same stream as this key)."
        )
    else:
        same = (
            "Open the **live stream detail** you created "
            "(same one as this key)."
        )
    print(
        f"""
FFmpeg is publishing. When MediaMTX shows the path online / HLS converting:

### Do this on your phone now

1. {same}
2. Tap **Refresh health** — expect playlist present / live (may take ~5–10s).
3. Tap **Issue playback token** (or Play).
4. Video should start (looping test clip).
5. Optional: on PC open http://127.0.0.1:8000/demo/ and paste the playback URL.
6. When done: tap **Revoke** in the app, or Ctrl+C here
   (revokes automatically if this script created the stream).

Leave this process running until you've confirmed play.
"""
    )


def build_ffmpeg_cmd(video: Path, rtmp_url: str) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found on PATH")
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        str(video),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-c:a",
        "aac",
        "-f",
        "flv",
        rtmp_url,
    ]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Publish a looping sample to OnStream live RTMP and print phone steps."
        )
    )
    p.add_argument(
        "--stream-key",
        help="Plaintext stream key from Expo create (skips API create).",
    )
    p.add_argument(
        "--stream-id",
        help="Optional stream_id for checklist (when using --stream-key).",
    )
    p.add_argument("--username", default=os.environ.get("ONSTREAM_LAB_USER", ""))
    p.add_argument("--password", default=os.environ.get("ONSTREAM_LAB_PASSWORD", ""))
    p.add_argument("--title", default="Live lab (FFmpeg)")
    p.add_argument("--base-url", default=DEFAULT_BASE)
    p.add_argument(
        "--rtmp-base",
        default=DEFAULT_RTMP,
        help="e.g. rtmp://127.0.0.1:1935/live",
    )
    p.add_argument("--mediamtx-api", default=DEFAULT_MTX)
    p.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    p.add_argument(
        "--revoke-on-exit",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Revoke on Ctrl+C (default: yes if this script created the stream).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    video = args.video if args.video.is_absolute() else (ROOT / args.video)
    if not video.is_file():
        raise SystemExit(f"Missing sample video: {video}")

    token: str | None = None
    stream_id: str | None = args.stream_id
    stream_key: str | None = args.stream_key
    created_by_script = False

    if stream_key:
        print("[mode] Using provided --stream-key (Expo/Scalar create).")
    else:
        if not args.username or not args.password:
            raise SystemExit(
                "Provide --stream-key KEY, or --username/--password "
                "(or ONSTREAM_LAB_USER / ONSTREAM_LAB_PASSWORD) to create a stream."
            )
        print(f"[mode] Create stream via API at {args.base_url}")
        st, _ = api("GET", args.base_url, "/health")
        if st != 200:
            raise SystemExit(f"API health failed HTTP {st}")
        token = login(args.base_url, args.username, args.password)
        created = create_stream(args.base_url, token, args.title)
        stream_id = created["stream_id"]
        stream_key = created["stream_key"]
        created_by_script = True
        print(f"[ok] created stream_id={stream_id}")

    assert stream_key
    rtmp_base = args.rtmp_base.rstrip("/")
    rtmp_url = f"{rtmp_base}/{stream_key}"
    # OnStream / MediaMTX path is always live/{stream_key} for RTMP publish.
    path_name = f"live/{stream_key}"

    print_banner(stream_id, stream_key, rtmp_url, video)
    cmd = build_ffmpeg_cmd(video, rtmp_url)
    print("[ffmpeg]", " ".join(cmd), flush=True)
    print("[info] Starting publisher…\n", flush=True)
    # Keep ffmpeg stderr quiet on progress (-nostats) so status lines stay readable.
    proc = subprocess.Popen(cmd)

    try:
        if wait_path_online(args.mediamtx_api, path_name):
            print(f"\n[ok] MediaMTX path online: {path_name}", flush=True)
        else:
            print(
                f"\n[warn] MediaMTX path not confirmed yet ({path_name}). "
                "If publish auth failed, check API + MediaMTX logs.",
                flush=True,
            )
        print_phone_checklist(stream_id)
        print("[info] Publishing… Ctrl+C to stop.\n", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        print("\n[info] Stopping FFmpeg…", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

    revoke = args.revoke_on_exit
    if revoke is None:
        revoke = created_by_script
    if revoke and stream_id and token:
        revoke_stream(args.base_url, token, stream_id)
    elif revoke and stream_id and not token:
        print(
            "[warn] --revoke-on-exit needs API login; "
            "revoke from Expo or pass --username/--password."
        )
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
