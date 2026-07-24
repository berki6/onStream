# API reference map (`/v1`)

Index: [`README.md`](README.md).

This document is the route catalogue for OnStream’s public HTTP surface. Interactive exploration is available on the running server at:

| UI | URL |
|----|-----|
| Scalar API reference | [`/scalar`](http://localhost:8000/scalar) (recommended) |
| Swagger UI | [`/docs`](http://localhost:8000/docs) |
| ReDoc | [`/redoc`](http://localhost:8000/redoc) |

Architectural context lives in [`FOUNDATION.md`](FOUNDATION.md); behavioral detail for media and live flows lives in the sibling design documents.

Unless noted, JSON **success** responses use `{ success, data, message, request_id, timestamp, api_version }`. List endpoints may add `pagination`. Authenticate with `Authorization: Bearer <access_token>` or, where supported, `X-API-Key: <key>`.

## Error envelope (breaking)

All `/v1` errors (except MediaMTX auth webhook, which returns bare status) use:

```json
{
  "success": false,
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "Incorrect username or password",
    "details": null
  },
  "request_id": "...",
  "timestamp": "...",
  "api_version": "v1"
}
```

`422` validation failures set `error.code` to `VALIDATION_FAILED` and populate `details` with `{field, message, code}` entries. There is no FastAPI `detail` key.

### Error code catalogue

| Code | HTTP | Meaning |
|------|------|---------|
| `AUTH_USERNAME_TAKEN` | 400 | Register username conflict |
| `AUTH_EMAIL_TAKEN` | 400 | Register email conflict |
| `AUTH_INVALID_CREDENTIALS` | 401 | Bad login |
| `AUTH_INVALID_TOKEN` | 401/400 | Refresh or password-reset token |
| `AUTH_UNAUTHORIZED` | 401 | Missing/invalid access credentials |
| `VIDEO_NOT_FOUND` | 404 | Video missing |
| `VIDEO_FORBIDDEN` | 403 | Not owner / no access |
| `VIDEO_BAD_REQUEST` | 400 | Invalid validation |
| `VIDEO_TOO_LARGE` | 413 | Upload size |
| `VIDEO_INVALID_FILE` | 400 | Corrupt / unreadable media |
| `UPLOAD_SESSION_NOT_FOUND` | 404 | Direct upload session |
| `UPLOAD_SESSION_GONE` | 410 | Session expired |
| `UPLOAD_BAD_REQUEST` | 400 | Empty/invalid chunk |
| `UPLOAD_TOO_LARGE` | 413 | Chunk exceeds limit |
| `UPLOAD_OBJECT_MISSING` | 400 | Object not in storage |
| `PLAYBACK_NOT_READY` | 409 | ABR not ready |
| `PLAYBACK_FORBIDDEN` | 403 | Playback denied |
| `PLAYBACK_UNAUTHORIZED` | 401 | Missing stream token |
| `PLAYBACK_NOT_FOUND` | 404 | Playlist/segment missing |
| `PLAYBACK_BAD_REQUEST` | 400 | Bad segment name |
| `LIVE_DISABLED` | 403 | Live feature off |
| `LIVE_NOT_FOUND` | 404 | Stream missing |
| `LIVE_FORBIDDEN` | 403 | Live access denied |
| `LIVE_UNAUTHORIZED` | 401 | Live playback auth |
| `JOB_NOT_FOUND` | 404 | Job missing |
| `JOB_CONFLICT` | 409 | Retry/cancel not allowed |
| `JOB_BAD_REQUEST` | 400 | Unknown job action/type |
| `JOB_FAILED` | 500 | Worker processing failure |
| `PLAYLIST_NOT_FOUND` | 404 | Playlist missing |
| `PLAYLIST_FORBIDDEN` | 403 | Playlist access |
| `PLAYLIST_CONFLICT` | 409/400 | Name taken / state conflict |
| `PLAYLIST_BAD_REQUEST` | 400 | Playlist params |
| `WEBHOOK_NOT_FOUND` | 404 | Webhook missing |
| `API_KEY_NOT_FOUND` | 404 | API key missing |
| `SEARCH_BAD_REQUEST` | 400 | Search params |
| `MODERATION_CONFLICT` | 409 | Not quarantined |
| `MODERATION_BAD_REQUEST` | 400 | Moderation input |
| `MODERATION_FORBIDDEN` | 403 | Moderation access |
| `CAPTION_NOT_FOUND` | 404 | Caption asset |
| `CAPTION_FORBIDDEN` | 403 | Caption access |
| `VALIDATION_FAILED` | 422 | Request body/schema |
| `VALIDATION_INVALID_ID` | 400 | Public id format |
| `VALIDATION_BAD_REQUEST` | 400 | Generic validation |
| `RATE_LIMIT_EXCEEDED` | 429 | Auth rate limit |
| `INTERNAL_SERVER_ERROR` | 500 | Unhandled / generic server |
| `INTERNAL_STORAGE_FAILURE` | 500 | Object storage I/O |
| `INTERNAL_QUEUE_FAILURE` | 500 | Queue bookkeeping |

Job rows (`video_jobs` / `queued_jobs`) and `video.failed` webhooks also carry `error_code` when a worker fails.

```mermaid
flowchart TB
  Client --> Auth["/v1/auth"]
  Client --> Videos["/v1/videos + /uploads"]
  Client --> Play["/v1/playback"]
  Client --> Live["/v1/live"]
  Client --> More["webhooks api-keys playlists moderation search"]
  MTX[MediaMTX] --> LiveAuth["/v1/live/mediamtx-auth"]
```

## Auth — `/v1/auth`

Registration and login establish control-plane credentials. Login uses OAuth2 password form encoding for compatibility with OpenAPI password flows; other auth routes accept JSON.

| Method | Path | Notes |
|--------|------|--------|
| POST | `/register` | JSON username, email, password |
| POST | `/login` | **form-urlencoded** username/password |
| POST | `/token/refresh` | JSON refresh_token |
| POST | `/password-reset` | JSON email |
| POST | `/password-reset/confirm` | token + new password |

## Videos — `/v1/videos`

Video identifiers in paths are public `upload_id` values. Multipart create is the convenience upload; prefer `/v1/uploads` for large or resumable transfers ([`MEDIA_CORE.md`](MEDIA_CORE.md)).

| Method | Path |
|--------|------|
| GET | `/` list |
| POST | `/` multipart upload |
| GET | `/{video_id}` |
| PATCH | `/{video_id}` |
| DELETE | `/{video_id}` |
| POST | `/{video_id}/tokens` signed playback |
| GET | `/{video_id}/job` (jobs router) |
| GET | `/{video_id}/chapters` |

## Uploads — `/v1/uploads`

Direct upload separates session creation, byte transfer, and completion so clients can retry `PUT`s without re-creating metadata.

| Method | Path |
|--------|------|
| POST | `/` create session |
| PUT | `/{session_id}` body bytes |
| POST | `/{session_id}/complete` |

## Playback

Playback routes serve HLS masters and assets for VOD and live. Authorization accepts a stream token query parameter, a Bearer token, or public visibility. Playlist responses rewrite child URLs so tokens propagate to segments.

| Method | Path |
|--------|------|
| GET | `/v1/playback/{video_id}/master.m3u8` |
| GET | `/v1/playback/{video_id}/{asset}` |
| GET | `/v1/playback/live/{stream_id}/master.m3u8` |
| GET | `/v1/playback/live/{stream_id}/{asset}` |

## Live — `/v1/live`

Create returns sensitive publish material once (`stream_key`, `whip_url`, `whep_url`). MediaMTX calls `/mediamtx-auth` on publish and read. Operational recipes: [`PLAYBACK_CLIENTS.md`](PLAYBACK_CLIENTS.md).

| Method | Path |
|--------|------|
| POST | `/` create (returns stream_key, whip_url, whep_url once) |
| GET | `/` list |
| GET | `/{stream_id}` |
| GET | `/{stream_id}/health` |
| DELETE | `/{stream_id}` |
| POST | `/{stream_id}/tokens` |
| POST | `/mediamtx-auth` MediaMTX webhook |

## Other `/v1` routers

| Prefix | Purpose |
|--------|---------|
| `/webhooks` | endpoint CRUD + deliveries |
| `/api-keys` | API key management |
| `/playlists` | user playlists |
| `/moderation` | quarantine queue + review |
| `/search` | keyword / semantic search |

## Non-`/v1` operational endpoints

These routes are mounted on the application root for probes, metrics scrapers, and the optional demo player.

| Path | Purpose |
|------|---------|
| `/health` | deep health |
| `/health/live` | liveness |
| `/health/ready` | readiness |
| `/metrics` | Prometheus (if enabled) |
| `/scalar` | Scalar interactive API reference |
| `/demo/` | static hls.js (if `DEMO_PLAYER_ENABLED`) |

## Client guides

[`PLAYBACK_CLIENTS.md`](PLAYBACK_CLIENTS.md) · [`onstream-demo/README.md`](../onstream-demo/README.md)
