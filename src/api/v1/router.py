from fastapi import APIRouter

from src.api.v1.routes import (
    api_keys,
    auth,
    jobs,
    playback,
    playlists,
    uploads,
    videos,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(jobs.router, prefix="/videos", tags=["jobs"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(playback.router, prefix="/playback", tags=["playback"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
