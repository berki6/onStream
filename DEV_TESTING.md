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
