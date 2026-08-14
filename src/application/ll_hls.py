"""Apple LL-HLS playlist helpers (blocking reload + part URI rewrite).

Default live playback stays the EVENT DVR archive. LL is a separate sliding
playlist under ``{stream_id}/ll/``. Blocking ``_HLS_msn`` / ``_HLS_part`` holds
the GET until that part exists (or the timeout), matching Apple's reload.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

_MEDIA_SEQ = re.compile(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", re.I)
_PART = re.compile(r"#EXT-X-PART:", re.I)
_URI_ATTR = re.compile(r'(URI=")([^"]+)(")', re.I)


def is_ll_playlist(text: str) -> bool:
    return "#EXT-X-PART:" in (text or "") or "#EXT-X-SERVER-CONTROL:" in (text or "")


def media_sequence(text: str) -> int:
    m = _MEDIA_SEQ.search(text or "")
    return int(m.group(1)) if m else 0


def latest_msn_part(text: str) -> Tuple[int, int]:
    """Return (msn, part) of the newest media the playlist can satisfy.

    Complete segments occupy ``MEDIA-SEQUENCE + index``. PART tags after the
    last URI belong to the *next* msn (Apple blocking reload).
    """
    msn = media_sequence(text or "")
    complete = 0
    trailing_parts = -1
    current_parts = -1
    for raw in (text or "").splitlines():
        line = raw.strip()
        if _PART.match(line):
            current_parts += 1
            trailing_parts = current_parts
        elif line and not line.startswith("#"):
            complete += 1
            current_parts = -1
            trailing_parts = -1
    if complete:
        last_complete = msn + complete - 1
        if trailing_parts >= 0:
            return last_complete + 1, trailing_parts
        return last_complete, 0
    return msn, max(trailing_parts, 0)


def has_reached(text: str, want_msn: int, want_part: int) -> bool:
    got_msn, got_part = latest_msn_part(text)
    if got_msn > want_msn:
        return True
    if got_msn == want_msn and got_part >= want_part:
        return True
    return False


def wait_for_playlist(
    path: Path,
    *,
    msn: Optional[int],
    part: Optional[int],
    timeout: float = 2.5,
) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise FileNotFoundError(str(path)) from exc
    if msn is None or not is_ll_playlist(text):
        return text
    want_part = int(part or 0)
    want_msn = int(msn)
    deadline = time.time() + max(0.05, timeout)
    while time.time() < deadline:
        if has_reached(text, want_msn, want_part):
            return text
        time.sleep(0.05)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            break
    return text


def append_token_to_quoted_uris(content: str, token: str) -> str:
    """Tokenize URI= attributes on PART / PRELOAD-HINT / MAP tags."""
    if not token:
        return content
    q = f"token={quote(token)}"

    def repl(match: re.Match[str]) -> str:
        uri = match.group(2)
        if "token=" in uri:
            return match.group(0)
        if uri.startswith("http") or uri.startswith("data:"):
            return match.group(0)
        tagged = f"{uri}&{q}" if "?" in uri else f"{uri}?{q}"
        return f"{match.group(1)}{tagged}{match.group(3)}"

    return _URI_ATTR.sub(repl, content)
