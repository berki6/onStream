"""Sync LAN IP into local .env files for phone / Expo lab testing.

Detects this machine's LAN address and rewrites only uncommitted lab env files:
  - .env                         → PUBLIC_API_BASE_URL, PUBLIC_WEBRTC_BASE_URL
  - onstream-demo/.env           → EXPO_PUBLIC_API_BASE_URL

Does **not** touch committed examples/docs (``.env.example``, ``DEV_TESTING.md``).

Usage (repo root):

  .\\.venv\\Scripts\\python.exe scripts/sync_lan_ip.py
  .\\.venv\\Scripts\\python.exe scripts/sync_lan_ip.py --dry-run
  .\\.venv\\Scripts\\python.exe scripts/sync_lan_ip.py --ip 192.168.1.10
  .\\.venv\\Scripts\\python.exe scripts/sync_lan_ip.py --https

--https keeps Expo/API on http://LAN:8000 and points WHIP at https://LAN
(Caddy). Generate certs with scripts/lab_https.py.

Restart the API after changing .env. Restart Expo (or Lab → Save API URL)
so the phone picks up EXPO_PUBLIC_API_BASE_URL. Restart MediaMTX if WHIP
publish from a phone/browser on LAN must hit PUBLIC_WEBRTC_BASE_URL.
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IPV4_RE = re.compile(r"\d{1,3}(\.\d{1,3}){3}")

# Match lab URLs we previously wrote (IPv4 LAN only — leave localhost alone).
# Keep these exact (port required) so :8000 is never rewritten into :8889.
LAN_API_RE = re.compile(r"http://192\.168\.\d+\.\d+:8000")
LAN_WEBRTC_RE = re.compile(r"http://192\.168\.\d+\.\d+:8889")
# Also upgrade a localhost PUBLIC/EXPO/WEBRTC base if someone left the template default.
LOCALHOST_API_RE = re.compile(
    r"((?:PUBLIC_API_BASE_URL|EXPO_PUBLIC_API_BASE_URL)=)http://localhost:8000"
)
LOCALHOST_WEBRTC_RE = re.compile(
    r"(PUBLIC_WEBRTC_BASE_URL=)http://localhost:8889"
)

TARGETS = [
    ROOT / ".env",
    ROOT / "onstream-demo" / ".env",
]

def detect_lan_ip() -> str:
    """Best-effort primary LAN IPv4 (works on Windows / macOS / Linux)."""
    # UDP connect trick — no packets sent; OS picks the outbound interface.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            cand = info[4][0]
            if cand.startswith("192.168.") or cand.startswith("10."):
                return cand
    except OSError:
        pass

    raise SystemExit(
        "Could not detect a LAN IP. Pass one explicitly: --ip 192.168.x.x"
    )


def upsert_env(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def rewrite(text: str, ip: str) -> str:
    api = f"http://{ip}:8000"
    webrtc = f"http://{ip}:8889"
    out = LAN_API_RE.sub(api, text)
    out = LAN_WEBRTC_RE.sub(webrtc, out)
    out = LOCALHOST_API_RE.sub(rf"\g<1>{api}", out)
    out = LOCALHOST_WEBRTC_RE.sub(rf"\g<1>{webrtc}", out)
    return out


def rewrite_https(text: str, ip: str, *, include_webrtc: bool) -> str:
    """HTTP API for Expo; HTTPS origin for browser WHIP via Caddy."""
    out = rewrite(text, ip)
    if include_webrtc:
        origin = f"https://{ip}"
        out = upsert_env(out, "PUBLIC_HTTPS_BASE_URL", origin)
        out = upsert_env(out, "PUBLIC_WEBRTC_BASE_URL", origin)
        out = upsert_env(out, "ONSTREAM_LAN_IP", ip)
    return out


def patch_file(
    path: Path,
    ip: str,
    *,
    dry_run: bool,
    https: bool,
) -> bool:
    if not path.is_file():
        print(f"MISSING  {path.relative_to(ROOT)}")
        return False
    raw = path.read_text(encoding="utf-8")
    include_webrtc = https and path.name == ".env"
    updated = (
        rewrite_https(raw, ip, include_webrtc=include_webrtc)
        if https
        else rewrite(raw, ip)
    )
    if updated == raw:
        print(f"UNCHANGED {path.relative_to(ROOT)}")
        _print_api_lines(updated)
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"{'DRY-RUN ' if dry_run else ''}UPDATED  {path.relative_to(ROOT)}")
    _print_api_lines(updated)
    return True


def _print_api_lines(text: str) -> None:
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(
            r"^(?:PUBLIC_API_BASE_URL|EXPO_PUBLIC_API_BASE_URL|"
            r"PUBLIC_WEBRTC_BASE_URL|PUBLIC_HTTPS_BASE_URL|"
            r"ONSTREAM_LAN_IP)\s*=",
            stripped,
        ):
            try:
                print(f"         {stripped}")
            except UnicodeEncodeError:
                print(f"         {stripped.encode('ascii', 'replace').decode()}")


def apply_env(ip: str, *, https: bool, dry_run: bool) -> int:
    changed = 0
    for path in TARGETS:
        if patch_file(path, ip, dry_run=dry_run, https=https):
            changed += 1
    docker_env = ROOT / ".env.docker"
    if https and docker_env.is_file():
        raw = docker_env.read_text(encoding="utf-8")
        updated = rewrite_https(raw, ip, include_webrtc=True)
        # Issued browser URLs must be the LAN host; docker-internal MTX stays as-is.
        updated = upsert_env(updated, "PUBLIC_API_BASE_URL", f"http://{ip}:8000")
        if updated != raw:
            if not dry_run:
                docker_env.write_text(updated, encoding="utf-8", newline="\n")
            print(
                f"{'DRY-RUN ' if dry_run else ''}UPDATED  "
                f"{docker_env.relative_to(ROOT)}"
            )
            _print_api_lines(updated)
            changed += 1
        else:
            print(f"UNCHANGED {docker_env.relative_to(ROOT)}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync LAN IP into OnStream local .env files (not committed docs)"
    )
    parser.add_argument(
        "--ip",
        help="Force this IPv4 instead of auto-detect (e.g. 192.168.1.6)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="Point WHIP at https://LAN (Caddy); keep Expo on http://LAN:8000",
    )
    args = parser.parse_args()

    ip = args.ip or detect_lan_ip()
    if not IPV4_RE.fullmatch(ip):
        print(f"Invalid --ip: {ip}", file=sys.stderr)
        return 2

    print(f"LAN_IP={ip}")
    changed = apply_env(ip, https=args.https, dry_run=args.dry_run)

    print()
    if args.dry_run:
        print(f"Dry-run complete ({changed} file(s) would change).")
    else:
        print(f"Done ({changed} file(s) changed).")
        if args.https:
            print(
                "Next: python scripts/lab_https.py  then  "
                "caddy run --config deploy/Caddyfile.host --adapter caddyfile"
                "  (or docker compose --profile edge up caddy). Restart API."
            )
        else:
            print(
                "Next: restart API (uvicorn), MediaMTX if needed, "
                "and Expo / Lab -> Save API URL."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
