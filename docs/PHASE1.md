# Phase 1 — Production Foundation

Child of the OnStream 5-phase parent roadmap. Scope is foundation only.

## Goals

- Postgres-ready DB engine; Alembic is schema source of truth (no `create_all` at startup)
- Storage abstraction: `local` + `s3` (MinIO-compatible)
- Docker Compose: api, worker, postgres, redis, minio
- Auth: refresh tokens, password-reset flow, rate limits, configurable CORS
- Ops: Prometheus `/metrics`, optional Sentry, deeper health (storage + queue depth), soft-delete GC via storage, pytest `--cov=src`

## Exit criteria

`docker compose up` brings a clean stack; Alembic migrates empty Postgres; upload → process → stream works with local or MinIO storage.

## Out of scope

ABR, signed playback, webhooks, orgs/channels, AI, live (phases 2–5).
