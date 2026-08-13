# Local / Windows testing

## MediaMTX (live ingest)

**MediaMTX** is a lightweight media server (by bluenviron). For OnStream it is the **live ingest engine**: OBS publishes RTMP (or WHIP), MediaMTX remuxes to HLS/WebRTC, and OnStream only owns auth, stream IDs, playback URLs, and kick.

It is **not** part of the Python app — it runs as a separate process.

| Config | Use |
|--------|-----|
| [`configs/mediamtx.yml`](configs/mediamtx.yml) | Docker-oriented (`api:8000`, HLS `/hls`) |
| [`configs/mediamtx.windows.yml`](configs/mediamtx.windows.yml) | Local Windows — auth → `127.0.0.1:8000`, HLS → `data/live` |

MediaMTX on this machine: `C:\src\mediamtx\mediamtx.exe` (v1.20.0).

### Install (no Docker)

1. Download a Windows release from:  
   https://github.com/bluenviron/mediamtx/releases  
   (zip with `mediamtx.exe`)
2. Put it somewhere convenient (e.g. `C:\src\mediamtx\` or `C:\Tools\mediamtx\`).
3. Point it at this project’s **Windows** config (shared live HLS dir must match `LIVE_HLS_DIR`):

```powershell
C:\src\mediamtx\mediamtx.exe "C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream\configs\mediamtx.windows.yml"
```

Your `.env` already expects:

| Port | Role |
|------|------|
| `1935` | RTMP (OBS / FFmpeg) |
| `8554` | RTSP (FFmpeg normalize / ABR pull) |
| `8888` | HLS (internal) |
| `8889` | WebRTC WHIP/WHEP |
| `9997` | MediaMTX HTTP API (kick) |

Also ensure MediaMTX writes HLS into the same folder as `LIVE_HLS_DIR` (`data/live` in your `.env`) — that’s how the API serves `/v1/playback/live/...`. The Windows config sets `hlsDirectory` to this project’s `data/live`.

VOD does **not** need MediaMTX.

### Full live stack (3 terminals)

```powershell
# 1) API (must be up before publish — MediaMTX auth webhook)
cd C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream
.\.venv\Scripts\Activate.ps1
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 2) Worker
cd C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream
.\.venv\Scripts\Activate.ps1
python start_worker.py

# 3) MediaMTX
C:\src\mediamtx\mediamtx.exe "C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream\configs\mediamtx.windows.yml"
```

With API + worker + MediaMTX running, live create → OBS **or** FFmpeg publish → playback works.

---

## Demo surfaces (what to use)

| Surface | Path / URL | Role |
|---------|------------|------|
| **Expo lab** | [`onstream-demo/`](onstream-demo/) | Full product path: auth, VOD upload/play, live create/health/play/revoke |
| **Web hls.js player** | `http://localhost:8000/demo/` | Paste a signed HLS URL and play (captions + storyboard hover) |
| **Shared / embed watch** | `http://localhost:8000/demo/watch/?s=&t=` | Anonymous share landing; `embed=1` strips chrome for iframe |
| **Scalar** | `http://localhost:8000/scalar` | Interactive API (same as curl, in-browser) |
| **Swagger** | `http://localhost:8000/docs` | OpenAPI |

More encoder/player recipes: [`docs/PLAYBACK_CLIENTS.md`](docs/PLAYBACK_CLIENTS.md). Expo install notes: [`onstream-demo/README.md`](onstream-demo/README.md).

### Readiness

| Path | Status | Notes |
|------|--------|-------|
| Auth (Expo / Scalar) | **Ready** | Register, login, refresh, sign-out coded |
| VOD (Expo / API) | **Ready** | Upload → worker → READY → token → HLS (verified by `scripts/e2e_smoke.py`) |
| VOD on a **physical phone** | **Config** | `PUBLIC_API_BASE_URL` must be LAN IP (this machine: `http://192.168.43.246:8000`) |
| Live create / token / revoke | **Ready** | Verified by smoke; manual publish via OBS or FFmpeg (below) |
| `/demo/` | **Player + tools** | HLS player, storyboard hover, `/demo/watch/`, `/demo/whip/`, `/demo/whep/`, `/demo/upload/`, `/demo/reset/` |
| Captions in demo UI | **Ready** | Status + Open in `/demo/` for track menu; Expo player has no full track picker |
| Watch & collect | **Ready** | Unlisted visibility, playlists, instant clips, storyboard filmstrip, embed iframe, RSS feeds |
| Live list ended history | **Ready** | `include_ended=true`; Expo shows Active + Recently ended |
| Live → VOD replay | **Ready** | Revoke archives HLS; Expo **Watch replay** |
| Live HLS DVR scrub | **Ready** | EVENT archive is the live playlist; Expo **Jump to live** |
| Direct upload `/v1/uploads` | **Ready** | Expo **+** → **Resumable** + `/demo/upload/` (chunked Content-Range) |
| WHIP publish | **Ready (browser)** | `/demo/whip/` + Expo **Go Live** opens it; Expo Go has no native WebRTC encoder |
| WHEP watch | **Ready (PC Chrome)** | Tokenized `/demo/whep/?stream=&token=`; Expo **Watch live (low latency)** opens it; Expo Go has no WebRTC player |
| Password reset UX | **Ready** | Expo forgot/reset + `/demo/reset/`; `EMAIL_PROVIDER=log` (lab) / `smtp` (prod) |
| Moderation review | **Ready** | Lab → Moderation queue (approve / reject) |

**Critical DB fix (was blocking VOD):** Postgres `videostatus` enum was missing `PROCESSING`. Migration `f6a7b8c9d0e1` adds it.

**Watch & collect:** migration `i9c0d1e2f3a4` adds `videos.visibility` and share-link `clip_start_seconds` / `clip_end_seconds`. Run `alembic upgrade head` before testing unlisted, clips, or RSS.

---

## Prerequisites

1. Postgres up, DB `onstream`, migrations: `alembic upgrade head` (must include `PROCESSING` on `videostatus`, `i9c0d1e2f3a4` visibility/clips, and `j0a1b2c3d4e5` live → VOD archive)
2. Redis reachable (`REDIS_URL` in `.env`, e.g. WSL → `127.0.0.1:6379`)
3. FFmpeg on `PATH` (VOD transcode)
4. Python venv activated; deps installed (`requirements.txt`; AI path needs `requirements-ai.txt` if testing captions)
5. `.env` flags for demos (LAN IP example for this machine):

```env
DEMO_PLAYER_ENABLED=true
LIVE_ENABLED=true
PUBLIC_API_BASE_URL=http://192.168.43.246:8000
```

**Phone / Expo Go on device:** `PUBLIC_API_BASE_URL` and Expo’s API base must both use the PC’s LAN IP (not `localhost`). Restart the API after changing `.env`.

When your Wi‑Fi IP changes, from repo root:

```powershell
.\.venv\Scripts\python.exe scripts/sync_lan_ip.py
```

Updates only local `.env` and `onstream-demo/.env` (not committed examples/docs).  
(`--dry-run` / `--ip 192.168.x.x` available.) Then restart API + Expo.

Tokenized `playback_url` values are built from `PUBLIC_API_BASE_URL`. Expo’s in-app API base alone is not enough — the player follows the URL returned by the API.

---

## Step-by-step: start the stack

### Terminal 1 — API

```powershell
cd C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream
.\.venv\Scripts\Activate.ps1
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Smoke:

- `http://localhost:8000/health`
- `http://localhost:8000/scalar`
- `http://localhost:8000/demo/` (needs `DEMO_PLAYER_ENABLED=true`)

### Terminal 2 — Worker (required for VOD; also live health jobs)

```powershell
python start_worker.py
```

### Terminal 3 — MediaMTX (live only)

```powershell
C:\src\mediamtx\mediamtx.exe "C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream\configs\mediamtx.windows.yml"
```

### Terminal 4 — Expo demo (optional but recommended)

```powershell
cd C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream\onstream-demo
npm install
npm start
```

Scan the QR with **Expo Go** (same Wi‑Fi).

If Android shows **`Failed to download remote update`**, the phone cannot reach Metro. Prefer:

```powershell
# USB cable + debugging (device already attached)
adb reverse tcp:8081 tcp:8081
npm run start:usb
```

or `npm run start:tunnel`. Full guide (any Expo/RN Android project): [`docs/ANDROID_METRO_CONNECTION.md`](docs/ANDROID_METRO_CONNECTION.md).

Scan the QR with **Expo Go** (same Wi‑Fi).

| Client | API base to set in Account / login |
|--------|--------------------------------|
| Physical phone | `http://<YOUR-LAN-IP>:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator / PC browser | `http://localhost:8000` |

Optional default: copy `onstream-demo/.env.example` → `.env` and set `EXPO_PUBLIC_API_BASE_URL` (already points at `192.168.1.3` in the example).

### Automated API smoke (after stack is up)

```powershell
# once: tiny sample clip
ffmpeg -y -f lavfi -i testsrc=duration=2:size=320x240:rate=30 -f lavfi -i sine=frequency=1000:duration=2 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest data\e2e-sample.mp4

.\.venv\Scripts\python.exe scripts\e2e_smoke.py
```

Covers: health, `/demo/`, register/login, VOD upload→READY→master.m3u8, live create/health/token/revoke, MediaMTX API. Does **not** replace a real RTMP publish (OBS or FFmpeg).

---

## Step-by-step: auth

1. Open Expo → **Register** (email + password) or use Scalar `POST /v1/auth/register`.
2. **Sign in** → session stored (SecureStore).
3. Account → **Check /health** should succeed against your API base.
4. Sign out / sign back in to confirm refresh path.

---

## Step-by-step: VOD end-to-end

1. Ensure API + **worker** are running (MediaMTX not required).
2. Expo **Videos** → pick a short file → upload (multipart `/v1/videos/`).
3. Wait until status is **READY** (worker + FFmpeg).
4. Open the video → app requests a playback token and plays HLS via `expo-video`.
5. Alternate players:
   - Copy `playback_url` from Scalar `POST /v1/videos/{id}/tokens` → open in `/demo/` or VLC.
   - If captions ran, `/demo/` shows a **Captions** dropdown (and the video CC control) once the master includes `EXT-X-MEDIA TYPE=SUBTITLES`.
   - After transcode, hover the `/demo/` player for storyboard thumbs (`storyboard.vtt` + `.jpg` next to the master).
6. If phone play fails with network errors, fix `PUBLIC_API_BASE_URL` to the LAN IP and re-issue a token.
7. Optional Watch & collect (same READY video): edit **visibility**, add to a **playlist**, create a **clip** share, copy **RSS** / **embed** — see [§1c](#1c-watch--collect-playlists-unlisted-clips-storyboard-embed-rss).

---

## Step-by-step: live end-to-end

Shared setup, then pick **one** publisher (OBS or FFmpeg). Do not create a second stream mid-test — reuse the stream you just created.

### 1. Create the stream

1. Ensure API + worker + **MediaMTX** are running (API first — auth webhook).
2. Expo **Live** → **Create stream** (or Scalar `POST /v1/live`).
3. **Immediately copy** the plaintext stream key / RTMP URL / WHIP / WHEP (key is shown **once**).
4. Note the `stream_id` (needed for revoke / health).

### 2a. Publish with OBS

1. OBS → Settings → Stream:
   - Service: **Custom**
   - Server: `rtmp://127.0.0.1:1935/live` (or the RTMP URL from create)
   - Stream key: plaintext key from step 1
2. Start Streaming. MediaMTX should allow publish after OnStream auth.
3. Continue at [§3 Verify playback](#3-verify-playback).

### 2b. Publish with FFmpeg (no OBS)

**Preferred:** one helper that starts the looping publisher and prints the phone checklist. API + worker + MediaMTX must already be running.

It only automates the **encoder** side.

| Step | Mode B (`--username` / `--password`) | Mode A (`--stream-key`) |
|------|--------------------------------------|-------------------------|
| Create stream | Yes | No (you created in Expo) |
| Publish (FFmpeg loop) | Yes — keeps running | Yes — keeps running |
| Phone play / health / token | **You** | **You** |
| Revoke | On **Ctrl+C** (default) | Only if you pass login + `--revoke-on-exit` |

It waits while you test. It does **not** auto-play, auto-assert health, or revoke on a timer. Stop with Ctrl+C when you’re done — then mode B revokes.

```powershell
# A) You created the stream in Expo — paste the plaintext key (shown once):
.\.venv\Scripts\python.exe scripts\live_lab_publish.py --stream-key <STREAM_KEY>

# B) Script logs in, creates a stream, publishes, and revokes on Ctrl+C:
.\.venv\Scripts\python.exe scripts\live_lab_publish.py --username <user> --password <pass>
```

Optional env: `ONSTREAM_LAB_BASE`, `ONSTREAM_LAB_USER`, `ONSTREAM_LAB_PASSWORD`, `ONSTREAM_LAB_RTMP`, `ONSTREAM_LAB_MEDIAMTX_API`.

Expect script output: MediaMTX path online (when reachable), then **Do this on your phone now** steps. Leave it running until play is confirmed. `Ctrl+C` stops FFmpeg (and revokes in mode B by default).

**Manual fallback** (same encode settings):

```powershell
# Replace <STREAM_KEY> with the plaintext key from create (not stream_id)
ffmpeg -re -stream_loop -1 `
  -i "C:\Users\berek\OneDrive\Documents\DevFiles\Project-Python\onStream\tests\media\test-video.mp4" `
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast -tune zerolatency `
  -c:a aac -f flv `
  "rtmp://127.0.0.1:1935/live/<STREAM_KEY>"
```

Expect:

- FFmpeg keeps running (no fatal auth/disconnect errors)
- MediaMTX shows the path online and HLS converting under `LIVE_HLS_DIR` (`data/live`)

Leave FFmpeg running until playback is confirmed. Stop with `Ctrl+C` in that terminal (or `Stop-Process -Name ffmpeg`).

### 3. Verify playback

On the **same** stream detail (phone Expo, or PC players):

1. Tap **Refresh health** — expect playlist present / `live` (often ~5–10s after publish).
2. Tap **Issue playback token** (or Play).
3. Video should start (FFmpeg path loops `tests/media/test-video.mp4`).
4. Optional: paste the live `playback_url` into `http://localhost:8000/demo/` or open in VLC.

VLC tip: live HLS is a sliding window — the right-hand duration may look tiny while the left time climbs; that is normal.

### 4. Revoke (and what you should see)

Revoke ends the **OnStream** stream. It is not the same as stopping the encoder.

| How | Command / UI |
|-----|----------------|
| Expo | Live detail → **Revoke** |
| API | `DELETE /v1/live/<stream_id>` with user JWT |

```powershell
curl.exe -X DELETE "http://127.0.0.1:8000/v1/live/<stream_id>" `
  -H "Authorization: Bearer <access_token>"
```

What revoke does:

1. Marks the stream `ended` in the DB
2. Kicks the MediaMTX publisher by resolving `source.id` on the path, then `POST /v3/rtmpconns/kick/{id}` (or webrtc/srt equivalents). Soft-fails if the path is already idle
3. OnStream playback refuses that stream (`get_playable_stream` → not found)

What players should do (phone / VLC / `/demo/`):

- Buffered segments may play a few more seconds
- Next playlist refresh → **404** (`Live stream not found`)
- Picture stalls / errors; the live window does not continue

What may **not** stop:

- If kick soft-fails (MediaMTX down / unknown source type), FFmpeg/OBS can keep pushing RTMP
- Viewers still cannot watch via OnStream once status is `ended`

Owner GET of an ended stream still works (lab detail after revoke). Ended streams are omitted from the live list.

Confirmed check: `GET /v1/playback/live/<stream_id>/master.m3u8` → **404** after revoke.

After the revoke demo, stop the encoder (`Ctrl+C` / stop OBS) if it is still publishing.

### Live webhooks (optional integrator check)

With a webhook endpoint subscribed to `live.created,live.started,live.idle,live.ended` (or `*`):

1. Create / publish / unpublish / revoke as above (or use `scripts/live_lab_publish.py`).
2. Ensure the **worker** is running (delivers pending rows every few ticks).
3. Expect deliveries in order: `live.created` → `live.started` → (`live.idle` if encoder stops cleanly) → `live.ended` on revoke.

**Lab UI:** Expo **Lab** → Webhooks → Subscribe (e.g. `https://webhook.site/<uuid>`) → refresh **Delivery log**. Same data via `GET /v1/webhooks/deliveries`.

Hard `live.ended` is revoke-only; health soft-fail emits `live.idle`, not `live.ended`. Details: [`docs/API.md`](docs/API.md#live-outbound-webhooks).

---

## Quick checklist

- [ ] `/health` OK
- [ ] Register / login (Expo or Scalar)
- [ ] VOD upload → READY → play (Expo and/or `/demo/`)
- [ ] Optional: Watch & collect — unlisted play without token; playlist + play-next; clip share; storyboard; `/demo/watch/?embed=1`; RSS feed
- [ ] Live create → OBS **or** `scripts/live_lab_publish.py` / FFmpeg → play → revoke
- [ ] After revoke: playback 404; stop encoder if still running
- [ ] Phone: LAN `PUBLIC_API_BASE_URL` + matching Expo API base
- [ ] Optional: captions appear after AI jobs (Expo VOD detail shows READY vs captions-pending); on-disk `master.m3u8` gains `SUBTITLES`
- [ ] Optional: Lab → Webhooks subscribe + delivery log shows `live.*`
- [ ] Optional: Library → **+** → Resumable direct upload (or `/demo/upload/`) → READY
- [ ] Optional: Live create → **Go Live (WHIP in browser)** → camera publish (LAN `PUBLIC_WEBRTC_BASE_URL`)
- [ ] Optional: Lab → Moderation queue approve/reject
- [ ] Optional: Forgot password → log/SMTP → Expo reset screen

---

## Manual lab tests

### Before you start

Stack should already be up (API + worker + MediaMTX). In Expo **Account**, set API base to your LAN
(e.g. `http://192.168.1.6:8000`). Sign in as usual (`demo` / `DemoPass123!` if that’s your lab user).

**Fast pass order:** Direct upload → play → continue/resume → share link → playlists / unlisted / clip / storyboard / RSS → search → favorites → captions/`master.m3u8` → Forgot password → Live create → Go Live WHIP → play → Lab moderation (if you have a quarantine item).

---

### 1) Direct upload (`/v1/uploads`)

1. Expo → **Library**.
2. Tap **+** → pick a video → title → choose **Resumable** (chunked `/v1/uploads`; **Quick** is classic multipart).
3. Watch progress % → list refreshes → status goes PENDING → PROCESSING → **READY**.
4. Open the video → play HLS.

**Browser alt:** Lab → **Browser direct upload** (or `http://<LAN-IP>:8000/demo/upload/`) → paste a Bearer token from Scalar login → pick file → Upload.

---

### 1b) Continue watching, share links, search, favorites

1. On a READY video: **Issue playback / Play** and watch past ~10s (progress saves in the background).
2. Back to **Library** → **Continue watching** shelf appears only when there is progress (no empty shelf) → open a tile or **See all** → player resumes near last position. On See all: **✕** removes one item; **Clear all** clears in-progress only.
3. On video detail → heart (Saved) → Library **Saved** shelf lists it → **See all** for the full list; heart badge also shows on library rows. Unheart via ✕ or Clear all on Saved; **Clear** next to resume hint clears progress for that video.
4. Library → clock icon → **Watch history** (Clear all wipes history + continue). Empty state only on that screen, not as a Library shelf.
5. **Share link** → pick expiry + max views → Create & copy → prefer `app_url` (`onstream://watch?s=…&t=…`) in Expo, or browser `watch_url` (`/demo/watch/?s=…&t=…`) → video plays without login.
6. Revoke the link in the share sheet → reload watch URL → expired/revoked error.
7. Library → search icon → type a title keyword → ranked results → open video.
8. Video detail → pencil → edit title/description → Save; or Delete (confirm) → back to Library.
9. After captions/chapters jobs: detail **Chapters** list → tap a chapter → player seeks there.
10. Continue at [§1c](#1c-watch--collect-playlists-unlisted-clips-storyboard-embed-rss) for visibility, playlists, clips, storyboard, embed, RSS.

---

### 1c) Watch & collect (playlists, unlisted, clips, storyboard, embed, RSS)

Requires `alembic upgrade head` through `i9c0d1e2f3a4`. Use a **READY** VOD.

**Playlists**

1. Library → list icon (or **Playlists** shelf) → **+** → name a playlist.
2. Video detail → list icon → playlists with a check are already in; tap to add or remove.
3. Open the playlist → reorder with chevrons, remove with **✕**.
4. Play the first row (`?playlist=` + `?play=1`) → let it finish → next video should auto-open.

**Unlisted visibility**

1. Video detail → pencil → **Visibility** → **unlisted** → Save.
2. Library still shows it (owner list is unfiltered). Badge should read Unlisted.
3. Scalar: `GET /v1/playback/{upload_id}/master.m3u8` **without** a token → not 401 (READY HLS should 200).
4. `GET /v1/feeds/{username}/videos.rss` must **not** include this title. Switch visibility to **public** → refresh feed → title appears. **Private** still needs a token (401).

**Instant clips**

1. Video detail → scissors → set start/end (or tap a chapter) → **Preview start** → **Create clip share link**.
2. Open `watch_url` (`/demo/watch/?s=&t=`) — player should seek in and pause at end.
3. Share sheet also copies an **iframe** snippet (`embed=1`).

**Storyboard**

1. Confirm `data/hls/<upload_id>/storyboard.jpg` and `storyboard.vtt` exist (written at transcode).
2. After **Issue playback token**, Expo shows a **Scrub preview** filmstrip under the player — tap a tile to seek.
3. Paste the same `playback_url` into `http://localhost:8000/demo/` and hover the video for a sprite thumb.

**Embed**

1. From the share sheet, copy **Embed iframe**.
2. Or open `http://localhost:8000/demo/watch/?s=<public_id>&t=<token>&embed=1` — brand/kicker/home should be gone.
3. Optional: `&playlist=<id>` shows a side panel only if that playlist is **public**.

**RSS**

1. Account → copy **Public RSS** (`/v1/feeds/{username}/videos.rss`) — only `visibility=public` + READY items.
2. Playlist detail → **Make public** → copy **RSS feed** (`/v1/feeds/{username}/playlists/{id}.rss`).
3. Unlisted/private videos must not appear in either feed.

---

### 2) Captions on disk

1. Upload a short clip (Quick or Resumable) and wait until **READY**.
2. Wait for captions job (Expo detail may show captions-pending, then captions path).
3. On the PC, open: `data/hls/<upload_id>/master.m3u8`
4. Confirm it contains `TYPE=SUBTITLES` and `URI="captions.vtt"`.
5. Open playback in `/demo/` (or Expo “Open in demo”) → subtitle track menu should list captions.

---

### 3) Password reset (log driver)

1. Confirm `.env` has `EMAIL_PROVIDER=log`.
2. Expo login → **Forgot password?** → enter the account email → **Send reset**.
3. Non-prod: app should jump to **Reset** with token filled.  
   Or: read the API terminal for `email.sent` / the token / `onstream://reset?…`.
4. Set a new password → back to login → sign in with the new password.
5. **Browser alt:** `http://<LAN-IP>:8000/demo/reset/?token=…`

---

### 4) WHIP Go Live (camera → MediaMTX)

Camera must run in **PC Chrome** at `http://127.0.0.1:8000/demo/whip/` (Expo Go has no native WebRTC; browsers hide `getUserMedia` on insecure LAN HTTP). Expo **Go Live** still opens the page; copy the **PC camera link (localhost)** if the phone browser cannot capture.

1. Expo → Live → **New live** → Create stream (copy key/WHIP once if you want).
2. On the PC, open `/demo/whip/?whip=…` (or the localhost copy row) → Allow camera/mic → **Go Live**.
3. MediaMTX may log `MPEG-TS … MPEG-4 Audio only` for VP8/Opus — expected. OnStream normalizes to H.264+AAC HLS under `data/live/{stream_id}/`.
4. Back in Expo → **Open stream** → wait a few seconds for the first normalized playlist.
5. **Stop** on the WHIP page → revoke the stream when done.

Restart MediaMTX after pulling RTSP config (`rtsp: yes` on `:8554`). `LIVE_NORMALIZE_ENABLED` defaults on; FFmpeg must be on `PATH`.

If WHIP POST fails: browser must reach MediaMTX (`PUBLIC_WEBRTC_BASE_URL`). Restart API after any `sync_lan_ip` change.

---

### 5) Moderation review UI

1. Need a quarantined video (upload something that triggers moderation, or use an existing quarantined row from earlier tests).
2. Expo → **Lab** → **Moderation review queue**.
3. Toggle **Make public on approve** if you want.
4. **Approve** → video leaves queue; playback tokens work again.  
   Or **Reject** → stays blocked.
5. Confirm on Library / video detail status.

---

### 6) Live ingest normalize sidecar

Live ingest has a **normalize sidecar**: many codecs in, one H.264 + AAC HLS contract out. Playback prefers `{LIVE_HLS_DIR}/{stream_id}/index.m3u8`, so a crashed MediaMTX MPEG-TS muxer cannot win. WHEP stays on the raw ingest path.

**What happens on publish**

- **RTMP H.264 + AAC** — MediaMTX remux only. No extra encode.
- **WHIP VP8/Opus** (or H.264 + Opus) — FFmpeg pulls RTSP from MediaMTX and writes `data/live/{stream_id}/index.m3u8`.
- **Optional ABR** (`LIVE_ABR_ENABLED`) — same RTSP source; skips the single-rendition sidecar.

Auth still returns immediately. Track probing runs in a background thread so `/v1/live/mediamtx-auth` is not blocked. Live segments use `LIVE_HLS_SEGMENT_SECONDS` (default **1s**, separate from VOD `HLS_SEGMENT_SECONDS=4`). Expect about **3–6s** delay on Expo HLS. Sub-second needs WHEP in a browser (Expo Go has no WebRTC player).

**Retest WHIP**

1. Restart MediaMTX so `rtsp: yes` on `:8554` is loaded (`configs/mediamtx.windows.yml`). Uvicorn `--reload` should already have the Python changes.
2. Open **PC Chrome** at `http://127.0.0.1:8000/demo/whip/` (LAN HTTP still hides the camera).
3. Go live, then in Expo open the stream and wait a few seconds for the first normalized playlist.
4. A MediaMTX log line about MPEG-TS / MPEG-4 Audio is expected for VP8. Expo should play from the normalized HLS, not that muxer.

`LIVE_NORMALIZE_ENABLED` defaults on. FFmpeg must be on `PATH`. Hands-on camera steps: [§4](#4-whip-go-live-camera--mediamtx).

---

### 7) WHEP watch (sub-second, PC Chrome)

HLS on Expo stays ~3s. WHEP is a different protocol: authorized signaling through OnStream, media on MediaMTX.

1. Go live with WHIP ([§4](#4-whip-go-live-camera--mediamtx)) so the path is `live`.
2. Expo stream detail → **Issue live playback token** → copy **PC WHEP watch (localhost)** or tap **Watch live (low latency)**.
3. Open `http://127.0.0.1:8000/demo/whep/?stream=&token=` in **PC Chrome** (LAN HTTP is not a secure context for `RTCPeerConnection`).
4. **Watch** — should be near real-time vs the ~3s HLS player. Stop on the page when done.

The demo page POSTs SDP to `/v1/playback/live/{stream_id}/whep` (token in query). It never uses the create-once encoder `whep_url`.

---

### 8) Live → VOD replay

Requires `alembic upgrade head` (`j0a1b2c3d4e5`) and `LIVE_ARCHIVE_ENABLED=true`.

1. Go live (WHIP or RTMP) for at least a few seconds so archive segments exist.
2. Expo → issue a live playback token. HLS starts at the live edge; scrub the native timeline backward, then **Jump to live**.
3. `/demo/?url=` with the tokenized live master — hls.js timeline should seek within the EVENT playlist.
4. Expo → **Revoke stream**.
5. Same screen: **Watch replay** opens the Library VOD (`/video/{upload_id}`). HLS should play the recording; live playlist 404s.
6. Library list should show a new READY video with the live title.

Revoke without a dedicated archive playlist still ends the stream (`archived_upload_id` null). The sliding live window is never promoted.

---

## How these flows work (reference)

### Captions on disk
Worker injects `#EXT-X-MEDIA:TYPE=SUBTITLES` into `data/hls/{id}/master.m3u8` after VTT write (serve-time inject remains as a safety net).

### Password reset (Laravel-style mail)
- Local/lab: `EMAIL_PROVIDER=log` — full message (token + deep links) in API logs.
- Production: `EMAIL_PROVIDER=smtp` + `SMTP_*` (enforced; log/none rejected).
- Expo: Login → Forgot password → Reset (non-prod also returns `reset_token` in the API response).
- Browser: `/demo/reset/?token=…`

### Direct upload
- Expo Library → **+** → **Resumable** (chunked `PUT` + complete) or **Quick** (classic multipart).
- Browser: `/demo/upload/` with Bearer token.

### Live ingest / WHIP
- Sidecar design and retest: [§6](#6-live-ingest-normalize-sidecar). Camera walkthrough: [§4](#4-whip-go-live-camera--mediamtx). WHEP watch: [§7](#7-whep-watch-sub-second-pc-chrome).
- Expo Live create → **Go Live (WHIP in browser)** opens `/demo/whip/?whip=…`.
- Use **PC Chrome** at `http://127.0.0.1:8000/demo/whip/` for camera (LAN HTTP has no `getUserMedia`).
- VP8/Opus ingest is normalized to H.264+AAC HLS (`LIVE_NORMALIZE_ENABLED`, RTSP `:8554`). Viewer WHEP is `/demo/whep/?stream=&token=` (gateway); encoder `whep_url` is create-once only.
- Phone WHIP POST still needs LAN `PUBLIC_WEBRTC_BASE_URL`. `scripts/sync_lan_ip.py` updates this.
- OBS / FFmpeg / `scripts/live_lab_publish.py` still valid for RTMP (passthrough remux, no extra encode).

### Moderation
- Lab → **Moderation review queue** → approve / reject (optional make-public on approve).

### Watch & collect
- **Visibility:** `private` | `unlisted` | `public`. `is_public` is derived (`true` only when public). Unlisted is tokenless playback, omitted from RSS.
- **Clips:** share create / `POST /v1/videos/{id}/tokens` accept `clip_start` / `clip_end`. Stream JWT carries the window; master injects `#EXT-X-START`. Players seek/stop; no re-encode.
- **Storyboard:** transcode writes `storyboard.jpg` + `.vtt`; serve via `/v1/playback/{id}/storyboard.*`. Video GET and share exchange return tokenized URLs.
- **Playlists:** `PATCH /v1/playlists/{id}` (`name`, `is_public`); `GET /v1/playlists/public/{id}` for embeds. Expo: `/playlist`, Library shelf, add-to-playlist, play-next.
- **Embed:** `/demo/watch/?s=&t=&embed=1` (+ optional `playlist=`).
- **RSS:** `GET /v1/feeds/{username}/videos.rss` and `.../playlists/{id}.rss`.

---

## Out of scope / remaining limits

- Native in-app WHIP / WHEP — **Expo Go limit** (needs `expo-dev-client` + WebRTC); publish via `/demo/whip/`, watch via `/demo/whep/` on a secure origin
- Production SMTP inbox branding beyond text/HTML body already sent
- Multi-tenant admin moderation (queue is per authenticated owner)
