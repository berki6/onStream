# Documentation index

This directory is the canonical documentation set for the current OnStream codebase. Prefer these pages over material under [`Archive/`](Archive/), which is retained only for historical reference.

Each design document keeps structured reference tables and Mermaid diagrams, with explanatory sections that describe *why* the system is shaped that way—not only *what* exists.

```text
docs/
├── README.md              ← index (this file)
├── FOUNDATION.md          ← platform topology, packages, auth, storage
├── MEDIA_CORE.md          ← VOD upload → ABR → signed playback
├── REDIS_QUEUE.md         ← Redis queue, breaker, DB fallback, dispatch
├── PLAYBACK_CLIENTS.md    ← live design + VLC/OBS/WHIP/Expo recipes
├── OPS_MEDIA.md           ← CDN, NVENC, VMAF, metrics, Caddy
├── AI_MEDIA.md            ← post-transcode AI job graph
├── API.md                 ← /v1 route catalogue
├── SCHEMA.md              ← DB ERD + table map
└── Archive/               ← historical only — not product truth
```

## Recommended reading order

1. Root [`README.md`](../README.md) for installation and quick start.
2. [`FOUNDATION.md`](FOUNDATION.md) for process topology, authentication, and storage.
3. Choose a vertical:
   - VOD → [`MEDIA_CORE.md`](MEDIA_CORE.md) and [`REDIS_QUEUE.md`](REDIS_QUEUE.md)
   - Live → [`PLAYBACK_CLIENTS.md`](PLAYBACK_CLIENTS.md)
   - AI → [`AI_MEDIA.md`](AI_MEDIA.md)
   - Operations → [`OPS_MEDIA.md`](OPS_MEDIA.md)
4. Integrate against [`API.md`](API.md) and the live OpenAPI UI at `/docs`.
5. For schema work, use [`SCHEMA.md`](SCHEMA.md) together with Alembic.

## Product principles

- OnStream is a self-hosted Mux-style **media engine**, not a social application.
- Background work uses the custom Redis queue; Celery, Dramatiq, and Arq are out of scope.
- The public HTTP prefix is **`/v1`**; playback lives under `/v1/playback/...`.
- Live ingest is provided by **MediaMTX** (RTMP and WHIP/WHEP).

## Demonstration clients

| Surface | Documentation |
|---------|----------------|
| Static hls.js player at `/demo/` | [`PLAYBACK_CLIENTS.md`](PLAYBACK_CLIENTS.md) (`DEMO_PLAYER_ENABLED`) |
| Expo mobile lab | [`../onstream-demo/README.md`](../onstream-demo/README.md) |

## Archive

[`Archive/`](Archive/) contains frozen pre-`/v1` drafts. Do not copy API paths or architecture claims from it into new work.
