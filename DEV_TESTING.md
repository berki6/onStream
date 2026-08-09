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
| `1935` | RTMP (OBS) |
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

With API + worker + MediaMTX running, live create → OBS publish → playback works.

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
| Live create / token / revoke | **Ready** | Verified by smoke; OBS publish is the remaining manual step |
| `/demo/` | **Playback only** | Paste URL; no upload/login by design |
| Captions in demo UI | **Not in Expo** | Backend/AI can inject into playlist; demo does not show caption status |
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

Covers: health, `/demo/`, register/login, VOD upload→READY→master.m3u8, live create/health/token/revoke, MediaMTX API. Does **not** replace OBS publish.

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

1. Ensure API + worker + **MediaMTX** are running (API first — auth webhook).
2. Expo **Live** → **Create stream**.
3. **Immediately copy** stream key / RTMP URL / WHIP / WHEP (plaintext key is returned **once**).
4. OBS:
   - Service: Custom
   - Server: `rtmp://localhost:1935/live` (or the RTMP URL from create)
   - Stream key: the plaintext key from step 3
5. Start streaming in OBS. MediaMTX should allow publish after OnStream auth.
6. Expo live detail → health should move toward live; request playback token → play.
7. Alternate: paste live `playback_url` into `http://localhost:8000/demo/` or VLC.
8. **Revoke** in Expo → publisher should be kicked; playback stops accepting new viewers.

---

## Quick checklist

- [ ] `/health` OK
- [ ] Register / login (Expo or Scalar)
- [ ] VOD upload → READY → play (Expo and/or `/demo/`)
- [ ] Live create → OBS publish → play → revoke
- [ ] Phone: LAN `PUBLIC_API_BASE_URL` + matching Expo API base
- [ ] Optional: captions appear in master playlist after AI jobs (not shown in Expo UI)

---

## Out of scope for the demo UI

- Direct-upload browser flow (`/v1/uploads`) — use Scalar/curl if needed
- In-app WHIP publish — use OBS or a WHIP client with the copied URL
- Password-reset email UX in Expo
- Captions / moderation status screens
