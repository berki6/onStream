"""Mint mkcert lab TLS material for Caddy (phone camera / WHIP).

Caddy terminates HTTPS. MediaMTX keeps plain HTTP on :8889 for signaling
and UDP :8189 for ICE — those packets never go through Caddy.

Usage (repo root):

  .\\.venv\\Scripts\\python.exe scripts/lab_https.py
  .\\.venv\\Scripts\\python.exe scripts/lab_https.py --apply-env
  .\\.venv\\Scripts\\python.exe scripts/lab_https.py --ip 192.168.1.10 --apply-env

--apply-env rewrites local .env files (not committed examples):
  PUBLIC_API_BASE_URL / EXPO stay http://LAN:8000  (Expo Go cannot trust mkcert)
  PUBLIC_HTTPS_BASE_URL + PUBLIC_WEBRTC_BASE_URL = https://LAN
  ONSTREAM_LAN_IP = LAN  (Compose MTX_WEBRTCADDITIONALHOSTS)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import sync_lan_ip  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CERT_DIR = ROOT / "deploy" / "certs"
CERT_FILE = CERT_DIR / "lab.pem"
KEY_FILE = CERT_DIR / "lab-key.pem"
CA_FILE = CERT_DIR / "rootCA.pem"


def _which_mkcert() -> str:
    found = shutil.which("mkcert")
    if found:
        return found
    raise SystemExit(
        "mkcert not found on PATH.\n"
        "Install: https://github.com/FiloSottile/mkcert#installation\n"
        "Windows: choco install mkcert  OR  scoop install mkcert"
    )


def generate_certs(ip: str) -> None:
    mkcert = _which_mkcert()
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    # Trust on this PC so Chrome at https://LAN works without warnings.
    install = subprocess.run([mkcert, "-install"])
    if install.returncode != 0:
        print(
            "mkcert -install did not succeed (often needs an elevated shell). "
            "PC Chrome may warn until you re-run it; phones install rootCA.pem.",
            file=sys.stderr,
        )
    subprocess.run(
        [
            mkcert,
            "-cert-file",
            str(CERT_FILE),
            "-key-file",
            str(KEY_FILE),
            "localhost",
            "127.0.0.1",
            "::1",
            ip,
        ],
        check=True,
    )
    caroot = subprocess.check_output([mkcert, "-CAROOT"], text=True).strip()
    src = Path(caroot) / "rootCA.pem"
    if not src.is_file():
        raise SystemExit(f"mkcert CA not found at {src}")
    shutil.copyfile(src, CA_FILE)
    print(f"WROTE  {CERT_FILE.relative_to(ROOT)}")
    print(f"WROTE  {KEY_FILE.relative_to(ROOT)}")
    print(f"WROTE  {CA_FILE.relative_to(ROOT)}  (public CA only)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate mkcert certs for OnStream Caddy lab HTTPS"
    )
    parser.add_argument("--ip", help="LAN IPv4 (default: auto-detect)")
    parser.add_argument(
        "--apply-env",
        action="store_true",
        help="Rewrite local .env files for HTTPS WHIP + HTTP Expo API",
    )
    parser.add_argument(
        "--skip-certs",
        action="store_true",
        help="Only rewrite env (certs already exist)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ip = args.ip or sync_lan_ip.detect_lan_ip()
    if not sync_lan_ip.IPV4_RE.fullmatch(ip):
        print(f"Invalid --ip: {ip}", file=sys.stderr)
        return 2

    print(f"LAN_IP={ip}")
    if not args.skip_certs:
        if args.dry_run:
            print("DRY-RUN skip mkcert")
        else:
            generate_certs(ip)

    if args.apply_env:
        sync_lan_ip.apply_env(ip, https=True, dry_run=args.dry_run)

    print()
    print("Next:")
    print("  No Docker:  caddy run --config deploy/Caddyfile.host --adapter caddyfile")
    print("  Compose:    docker compose --profile edge up caddy")
    print(f"  Phone: open http://{ip}/lab/ca.crt and install the CA")
    print("     iOS: Profile + Certificate Trust Settings → Full Trust")
    print(f"  Phone Chrome/Safari: https://{ip}/demo/whip/?whip=…")
    print("  PC Chrome can still use http://127.0.0.1:8000/demo/whip/")
    print("  Restart the API after --apply-env.")
    print("Expo Go stays on http://LAN:8000 — it does not trust user CAs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
