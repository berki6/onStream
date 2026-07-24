# Media operations notes (live health, MediaMTX API, QoE, OTel)

## Live health

- Worker tick (every ~5 loops) runs `check_live_streams`.
- Streams with `status=live` whose playlist is **missing** are revoked (`ended`).
- Streams whose playlist **mtime age** exceeds `LIVE_STALE_SECONDS` (default 20) become `idle`.
- Emits webhook event `live.ended` with `{stream_id, status, reason}`.
- Owner API: `GET /v1/live/{stream_id}/health`.

Env:

```
LIVE_HEALTH_ENABLED=true
LIVE_STALE_SECONDS=20
```

## MediaMTX control API

- Config: `api: yes` / `apiAddress: :9997` in `configs/mediamtx.yml`.
- Compose exposes `9997`.
- Client: `src/infrastructure/live/mediamtx_client.py` (`get_path`, `kick_publisher`, `is_path_ready`).
- Soft-fails with warning logs when API is down.
- `DELETE /v1/live/{stream_id}` kicks publisher then stops ABR.

```
MEDIAMTX_API_URL=http://localhost:9997   # Docker: http://mediamtx:9997
MEDIAMTX_API_USER=
MEDIAMTX_API_PASS=
```

## Playback CDN headers

```
PLAYBACK_CDN_HEADERS_ENABLED=true
```

VOD playlists short-cache; VOD segments immutable; live playlists no-cache; live segments `max-age=2`.

## PyAV / OpenCV

```
MEDIA_PYAV_ENABLED=true
```

When enabled, `ffmpeg.probe_*`, caption audio extract, moderation/smart-thumbnail frame sampling prefer PyAV (+ numpy/OpenCV variance/Laplacian when installed via `requirements-ai.txt`). Shell ffmpeg remains the fallback.

## QoE canary

```
QOE_CANARY_ENABLED=true
```

Worker tick samples live playlist age + local file read latency into Prometheus histograms (`onstream_qoe_*`).

## OpenTelemetry

```
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

`setup_tracing()` runs from API `create_app` (and optionally the worker). Requires OTel packages from `requirements.txt`.

## Useful metrics

| Metric | Meaning |
|--------|---------|
| `onstream_live_streams_active` | Gauge of live streams |
| `onstream_live_playlist_age_seconds` | Playlist mtime age |
| `onstream_live_streams_stale_total` | Health transitions |
| `onstream_live_abr_active` | ABR processes |
| `onstream_live_auth_total` | MediaMTX auth allow/deny |
| `onstream_playback_responses_total` | Playback responses |
| `onstream_qoe_playlist_age_seconds` | QoE canary ages |
| `onstream_qoe_fetch_latency_seconds` | QoE local read latency |
