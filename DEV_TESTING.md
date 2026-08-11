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
| **Web hls.js player** | `http://localhost:8000/demo/` | Paste a signed HLS URL and play (no login) |
| **Scalar** | `http://localhost:8000/scalar` | Interactive API (same as curl, in-browser) |
| **Swagger** | `http://localhost:8000/docs` | OpenAPI |

More encoder/player recipes: [`docs/PLAYBACK_CLIENTS.md`](docs/PLAYBACK_CLIENTS.md). Expo install notes: [`onstream-demo/README.md`](onstream-demo/README.md).

### Readiness (honest)

| Path | Status | Notes |
|------|--------|-------|
| Auth (Expo / Scalar) | **Ready** | Register, login, refresh, sign-out coded |
| VOD (Expo / API) | **Ready** | Upload → worker → READY → token → HLS (verified by `scripts/e2e_smoke.py`) |
| VOD on a **physical phone** | **Config** | `PUBLIC_API_BASE_URL` must be LAN IP (this machine: `http://192.168.1.2:8000`) |
| Live create / token / revoke | **Ready** | Verified by smoke; manual publish via OBS or FFmpeg (below) |
| `/demo/` | **Playback only** | Paste URL; no upload/login by design |
| Captions in demo UI | **Ready (status)** | Video detail shows caption ready/pending + language; no in-player track picker yet |
| Direct upload `/v1/uploads` in Expo | **Not in Expo** | Multipart `/v1/videos/` only |
| WHIP publish from the app | **Not in Expo** | Copy WHIP URL → external encoder |

**Critical DB fix (was blocking VOD):** Postgres `videostatus` enum was missing `PROCESSING`. Migration `f6a7b8c9d0e1` adds it — run `alembic upgrade head` before testing VOD.

---

## Prerequisites

1. Postgres up, DB `onstream`, migrations: `alembic upgrade head` (must include `PROCESSING` on `videostatus`)
2. Redis reachable (`REDIS_URL` in `.env`, e.g. WSL → `127.0.0.1:6379`)
3. FFmpeg on `PATH` (VOD transcode)
4. Python venv activated; deps installed (`requirements.txt`; AI path needs `requirements-ai.txt` if testing captions)
5. `.env` flags for demos (LAN IP example for this machine):

```env
DEMO_PLAYER_ENABLED=true
LIVE_ENABLED=true
PUBLIC_API_BASE_URL=http://192.168.1.2:8000
```

**Phone / Expo Go on device:** `PUBLIC_API_BASE_URL` and Expo’s API base must both use the PC’s LAN IP (not `localhost`). Restart the API after changing `.env`.

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

| Client | API base to set in Lab / login |
|--------|--------------------------------|
| Physical phone | `http://<YOUR-LAN-IP>:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator / PC browser | `http://localhost:8000` |

Optional default: copy `onstream-demo/.env.example` → `.env` and set `EXPO_PUBLIC_API_BASE_URL` (already points at `192.168.1.2` in the example).

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
3. Lab / Settings → **Health ping** should succeed against your API base.
4. Sign out / sign back in to confirm refresh path.

---

## Step-by-step: VOD end-to-end

1. Ensure API + **worker** are running (MediaMTX not required).
2. Expo **Videos** → pick a short file → upload (multipart `/v1/videos/`).
3. Wait until status is **READY** (worker + FFmpeg).
4. Open the video → app requests a playback token and plays HLS via `expo-video`.
5. Alternate players:
   - Copy `playback_url` from Scalar `POST /v1/videos/{id}/tokens` → open in `/demo/` or VLC.
6. If phone play fails with network errors, fix `PUBLIC_API_BASE_URL` to the LAN IP and re-issue a token.

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

Hard `live.ended` is revoke-only; health soft-fail emits `live.idle`, not `live.ended`. Details: [`docs/API.md`](docs/API.md#live-outbound-webhooks).

---

## Quick checklist

- [ ] `/health` OK
- [ ] Register / login (Expo or Scalar)
- [ ] VOD upload → READY → play (Expo and/or `/demo/`)
- [ ] Live create → OBS **or** `scripts/live_lab_publish.py` / FFmpeg → play → revoke
- [ ] After revoke: playback 404; stop encoder if still running
- [ ] Phone: LAN `PUBLIC_API_BASE_URL` + matching Expo API base
- [ ] Optional: captions appear in master playlist after AI jobs (not shown in Expo UI)

---

## Out of scope for the demo UI

- Direct-upload browser flow (`/v1/uploads`) — use Scalar/curl if needed
- In-app WHIP publish — use OBS, FFmpeg (RTMP), or a WHIP client with the copied URL
- Password-reset email UX in Expo
- Captions / moderation status screens
