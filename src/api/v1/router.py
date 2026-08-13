from fastapi import APIRouter

from src.api.v1.error_responses import ERROR_RESPONSES
from src.api.v1.routes import (
    api_keys,
    auth,
    feeds,
    jobs,
    live,
    live_playback,
    moderation,
    playback,
    playlists,
    search,
    share_links,
    uploads,
    videos,
    webhooks,
)

api_router = APIRouter(responses=ERROR_RESPONSES)

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(jobs.router, prefix="/videos", tags=["jobs"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
# Live playback before generic /playback/{video_id} so "live" is not captured
api_router.include_router(
    live_playback.router, prefix="/playback/live", tags=["live-playback"]
)
api_router.include_router(playback.router, prefix="/playback", tags=["playback"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
api_router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
api_router.include_router(moderation.router, prefix="/moderation", tags=["moderation"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(
    share_links.router, prefix="/share-links", tags=["share-links"]
)