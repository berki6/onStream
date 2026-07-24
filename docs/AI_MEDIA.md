# AI Media Intelligence

OnStream can run optional post-transcode AI jobs: captions, chapters, moderation,
embeddings, and smart thumbnails. All AI work is **off by default** (`AI_ENABLED=false`)
so CI stays lightweight and GPU-free.

## Enabling

Set in `.env` / Compose:

```
AI_ENABLED=true
AI_CAPTIONS_PROVIDER=mock          # or faster_whisper
AI_EMBEDDINGS_PROVIDER=mock        # or sentence_transformers
AI_MODERATION_THRESHOLD=0.7
```

Feature flags (only apply when `AI_ENABLED=true`):

- `AI_CAPTIONS_ENABLED`
- `AI_CHAPTERS_ENABLED` (enqueued after captions)
- `AI_MODERATION_ENABLED` (parallel after transcode)
- `AI_EMBEDDINGS_ENABLED` (after captions)
- `AI_SMART_THUMBNAIL_ENABLED` (parallel after transcode)

Install optional packages:

```
pip install -r requirements-ai.txt
```

Docker profile:

```
docker compose --profile ai up worker-ai
```

## Job flow

1. Transcode completes → status `READY`
2. If AI enabled: enqueue `moderation`, `smart_thumbnail`, and `captions`
3. Captions done → write VTT + transcript; emit `video.captions_ready`; enqueue `chapters` + `embeddings`
4. Moderation score ≥ threshold → status `QUARANTINED`, `is_public=false`, emit `video.quarantined`

Queue payloads are JSON `{"upload_id","job_type"}` (legacy plain upload_id strings still work as `transcode`).

## APIs

- `GET /v1/moderation/queue` — quarantined videos for the current user
- `POST /v1/moderation/{video_id}/review` — `{ "action": "approve"|"reject", "make_public": true|false }`
- `GET /v1/search/?q=&mode=keyword|semantic&limit=`
- `GET /v1/videos/{video_id}/chapters`

Playback: quarantined videos are playable by the **owner only**. When `caption_vtt_path` is set, master playlists inject `#EXT-X-MEDIA:TYPE=SUBTITLES`.

## Mock providers

With `AI_CAPTIONS_PROVIDER=mock` / `AI_EMBEDDINGS_PROVIDER=mock`, handlers produce deterministic fake artifacts suitable for tests without ffmpeg Whisper or sentence-transformers.
