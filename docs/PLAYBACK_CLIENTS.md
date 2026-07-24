# Playback clients (VLC / OBS)

OnStream serves **HLS**. Use VLC or OBS as players; use OBS as a live encoder into MediaMTX.

## Efficiency notes (live)

1. **Default (efficient):** `LIVE_ABR_ENABLED=false` — MediaMTX remuxes one HLS ladder from OBS. Best for LAN / OBS→VLC.
2. **Optional:** `LIVE_ABR_ENABLED=true` — FFmpeg realtime multi-bitrate ABR (more CPU; better for remote/mobile viewers).
3. Do not enable live ABR only because VOD has ABR.

## VOD → VLC or OBS (already available)

1. Register/login: `POST /v1/auth/register`, `POST /v1/auth/login`.
2. Upload a video: `POST /v1/videos/` (multipart) or direct upload flow under `/v1/uploads`.
3. Wait until status is `READY` (job via worker).
4. Create a playback token:

```bash
curl -s -X POST "http://localhost:8000/v1/videos/{video_id}/tokens" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"playback"}'
```

5. Open the returned `playback_url` in:
   - **VLC:** Media → Open Network Stream → paste URL (includes `?token=...`).
   - **OBS:** Sources → Media Source → Local File unchecked → input the same HLS URL.

Public videos (`is_public=true`) can omit the token for VLC.

Example URL shape:

```text
http://localhost:8000/v1/playback/{video_id}/master.m3u8?token=...
```

## Live: OBS → MediaMTX → VLC

Requires Docker Compose with the `mediamtx` service (`docker compose up`).

### 1. Create a live stream

```bash
curl -s -X POST "http://localhost:8000/v1/live/" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"My live","is_public":false}'
```

Response includes (stream key shown **once**):

- `rtmp_url` — OBS server URL (e.g. `rtmp://localhost:1935/live`)
- `stream_key` — OBS stream key
- `playback_url` — HLS URL for VLC (may need a token if private)

### 2. Configure OBS

- Settings → Stream → Service: **Custom**
- Server: value of `rtmp_url` (typically `rtmp://localhost:1935/live`)
- Stream Key: value of `stream_key`
- Start Streaming

MediaMTX authenticates publish via `POST /v1/live/mediamtx-auth`.

### 3. Watch in VLC

Private streams — issue a token:

```bash
curl -s -X POST "http://localhost:8000/v1/live/{stream_id}/tokens" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Open `playback_url` in VLC (Network stream).

```text
http://localhost:8000/v1/playback/live/{stream_id}/master.m3u8?token=...
```

### 4. Stop / revoke

```bash
curl -s -X DELETE "http://localhost:8000/v1/live/{stream_id}" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

Revoking ends the stream key; further OBS publish fails auth; playback eventually 404s when HLS is gone.

## Ports (Compose)

| Port | Service |
|------|---------|
| 8000 | OnStream API + playback proxy |
| 1935 | MediaMTX RTMP (OBS) |
| 8888 | MediaMTX HLS (internal / debug; prefer OnStream `/v1/playback/live/...`) |

## Env kill switches

```
LIVE_ENABLED=true
LIVE_ABR_ENABLED=false
LIVE_ABR_LADDER=360:800,720:2500,1080:5000
PUBLIC_RTMP_BASE_URL=rtmp://localhost:1935/live
LIVE_HLS_DIR=data/live
LIVE_HEALTH_ENABLED=true
LIVE_STALE_SECONDS=20
PLAYBACK_CDN_HEADERS_ENABLED=true
```

## CDN / edge cache headers

When `PLAYBACK_CDN_HEADERS_ENABLED=true`, playback responses set `Cache-Control`:

| Asset | VOD | Live |
|-------|-----|------|
| `.m3u8` | `max-age=3` | `no-cache` / `no-store` |
| `.ts` | long `immutable` | `max-age=2` |

Owner health: `GET /v1/live/{stream_id}/health` (stale playlist age, ABR status).
