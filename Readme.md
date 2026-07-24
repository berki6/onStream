# OnStream

Self-hosted **Mux-ish video engine**: VOD ABR HLS, signed playback, OBS/browser live (MediaMTX RTMP + WHIP/WHEP), custom Redis job queue, optional AI and CDN purge.

API is **`/v1` only**. Public video id = `upload_id`.

## Quick start

```bash
# Local Python
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
# other terminal
python start_worker.py
```

```bash
# Full stack
docker compose up --build
```

- Swagger UI: http://localhost:8000/docs  
- Scalar API reference: http://localhost:8000/scalar  
- Compose also runs Postgres, Redis, MinIO, MediaMTX (RTMP `:1935`, WebRTC `:8889`)

Optional profiles: `ai`, `gpu`, `turn`, `edge` (Caddy), `obs` (Prometheus/Grafana).

## What it does

| Area | Capabilities |
|------|----------------|
| VOD | Direct/multipart upload → ABR HLS + storyboard → signed or public playback |
| Live | Create stream → OBS RTMP or WHIP → HLS/WHEP play → health + revoke |
| Jobs | Typed Redis queue + DB fallback (no Celery) |
| AI | Optional captions, chapters, moderation, embeddings (off by default) |
| Ops | structlog context, Prometheus, CDN purge (Cloudflare/Bunny), NVENC profile, VMAF gate |

## Mobile / browser demos

| Demo | Path |
|------|------|
| Web hls.js | `/demo/` when `DEMO_PLAYER_ENABLED=true` |
| Expo Go lab | [`onstream-demo/`](onstream-demo/) (SDK 54) |

## Documentation

Start at **[`docs/README.md`](docs/README.md)** (source of truth index).

| Doc | Topic |
|-----|--------|
| [docs/FOUNDATION.md](docs/FOUNDATION.md) | Platform topology, auth, storage |
| [docs/MEDIA_CORE.md](docs/MEDIA_CORE.md) | VOD design: upload → ABR → playback |
| [docs/REDIS_QUEUE.md](docs/REDIS_QUEUE.md) | Queue, circuit breaker, dispatch |
| [docs/PLAYBACK_CLIENTS.md](docs/PLAYBACK_CLIENTS.md) | Live design + VLC/OBS/WHIP/Expo |
| [docs/OPS_MEDIA.md](docs/OPS_MEDIA.md) | CDN, NVENC, VMAF, metrics, Caddy |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Storage / AI / email / CDN registries |
| [docs/AI_MEDIA.md](docs/AI_MEDIA.md) | AI job graph |
| [docs/API.md](docs/API.md) | `/v1` route map |
| [docs/SCHEMA.md](docs/SCHEMA.md) | DB ERD + table map |
| [docs/Archive/](docs/Archive/) | Historical notes (not maintained) |

## Tests

```bash
pytest tests/ -q --no-cov
```

## License

Pending.
