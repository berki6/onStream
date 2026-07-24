# Ops: media delivery (CDN, NVENC, quality, observability)

## CDN purge

OnStream can purge edge caches when a video is deleted, when a public video is made private, or when a live stream is revoked.

| Setting | Values |
|---------|--------|
| `CDN_PROVIDER` | `none` (default), `cloudflare`, `bunny` |
| `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ZONE_ID` | Cloudflare zone purge |
| `BUNNY_API_KEY` / `BUNNY_PULL_ZONE_ID` | Bunny.net URL purge |

Implementation: `src/infrastructure/cdn/` (`get_cdn_purger()`). Default is a no-op so local/dev stays quiet.

## NVENC (GPU encode)

1. Set `FFMPEG_HWACCEL=nvenc` on the worker.
2. Run the GPU profile:

```bash
docker compose --profile gpu up worker-gpu
```

`Dockerfile.gpu` sets `FFMPEG_HWACCEL=nvenc`. Stock apt FFmpeg often lacks NVENC; on production GPU hosts, use an NVENC-enabled FFmpeg (or NVIDIA CUDA base + custom build).

`encode_rendition` tries `h264_nvenc` first; on failure it retries with `libx264`.

## Quality gate (VMAF / PSNR)

| Setting | Default |
|---------|---------|
| `QUALITY_GATE_ENABLED` | `false` |
| `QUALITY_GATE_STRICT` | `false` |
| `QUALITY_GATE_MIN_VMAF` | `70` |

When enabled, the transcode worker scores the top rung vs source via `src/infrastructure/media/quality.py` (libvmaf, else PSNR). Score is stored on `videos.quality_score`. Low scores emit webhook event `video.quality`. With `QUALITY_GATE_STRICT=true`, a failing gate fails the job.

Migration: `alembic upgrade head` (adds `quality_score`).

## Grafana / Prometheus (`obs` profile)

```bash
docker compose --profile obs up prometheus grafana
```

- Prometheus: `http://localhost:9090` (scrapes `api:8000/metrics`)
- Grafana: `http://localhost:3000` (admin/admin; Prometheus datasource provisioned)

Config lives under `deploy/prometheus.yml` and `deploy/grafana/provisioning/`.

## Structured logging

`structlog` merges bound context (`request_id`, `upload_id`, `stream_id`, `job_type`, `user_id`) into every log line. JSON in `ENV=production`; console-friendly otherwise. Use `bind_context(...)` / `clear_context()`.

## Related profiles

| Profile | Purpose |
|---------|---------|
| `ai` | AI captions/embeddings worker |
| `gpu` | NVENC worker |
| `turn` | coturn (+ optional `docker-compose.turn.yml`) |
| `edge` | Caddy reverse proxy |
| `obs` | Prometheus + Grafana |
