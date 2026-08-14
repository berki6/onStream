"""Live HLS playback routes under /playback/live/{stream_id}/..."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from src.api.v1.deps import get_optional_user
from src.api.v1.responses import raise_app_error
from src.application import live_service, live_whep, ll_hls, playback_service
from src.application.errors import AppError
from src.application.error_codes import ErrorCode
from src.application.playback_headers import cache_headers
from src.infrastructure.db.session import get_db

router = APIRouter()


def _bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def _origin(request: Request) -> str:
    return request.headers.get("Origin") or request.headers.get("Referer") or ""


def _inc_playback(kind: str) -> None:
    try:
        from src.core.metrics import PLAYBACK_RESPONSES

        PLAYBACK_RESPONSES.labels(kind=kind, live="true").inc()
    except Exception:
        pass


def _parse_msn(request: Request) -> tuple:
    msn_raw = request.query_params.get("_HLS_msn")
    part_raw = request.query_params.get("_HLS_part")
    msn = int(msn_raw) if msn_raw and str(msn_raw).isdigit() else None
    part = int(part_raw) if part_raw and str(part_raw).isdigit() else None
    return msn, part


async def _playlist_response(path, stream_token, token, request, *, inject_edge: bool):
    msn, part = _parse_msn(request)
    try:
        raw = await asyncio.to_thread(
            ll_hls.wait_for_playlist, path, msn=msn, part=part
        )
    except OSError:
        raise_app_error(
            AppError("Live playlist not available", code=ErrorCode.LIVE_NOT_FOUND)
        )
    if inject_edge and not ll_hls.is_ll_playlist(raw):
        raw = playback_service.inject_live_edge_start(raw)
    body = playback_service.rewrite_playlist(raw, stream_token or token)
    headers = cache_headers(
        live=True, asset_name=path.name, ll=ll_hls.is_ll_playlist(raw)
    )
    return StreamingResponse(
        iter([body]),
        media_type="application/vnd.apple.mpegurl",
        headers=headers,
    )


@router.get("/{stream_id}/master.m3u8")
async def live_master_playlist(
    stream_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        path = live_service.resolve_master(stream)
    except AppError as e:
        raise_app_error(e)
    _inc_playback("master")
    return await _playlist_response(
        path, stream_token, token, request, inject_edge=True
    )


@router.get("/{stream_id}/ll/master.m3u8")
async def live_ll_master_playlist(
    stream_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        path = live_service.resolve_master(stream, latency="ll")
    except AppError as e:
        raise_app_error(e)
    _inc_playback("ll_master")
    return await _playlist_response(
        path, stream_token, token, request, inject_edge=False
    )


@router.post("/{stream_id}/whep")
async def live_whep_offer(
    stream_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        hls_path = live_whep.require_live_whep(stream)
        sid = stream.stream_id
        raw = await request.body()
        if len(raw) > live_whep.MAX_SDP_BYTES:
            raise AppError("SDP offer too large", code=ErrorCode.PLAYBACK_BAD_REQUEST)
        db.close()
        answer, location = await live_whep.offer(
            sid, hls_path, raw.decode("utf-8", errors="replace"), stream_token or token
        )
    except AppError as e:
        raise_app_error(e)
    _inc_playback("whep")
    return Response(
        content=answer,
        status_code=201,
        media_type="application/sdp",
        headers={
            "Location": location,
            "Access-Control-Expose-Headers": "Location",
        },
    )


@router.delete("/{stream_id}/whep/sessions/{session_id}")
async def live_whep_stop(
    stream_id: str,
    session_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        sid = stream.stream_id
        db.close()
        await live_whep.stop(sid, session_id)
    except AppError as e:
        raise_app_error(e)
    _inc_playback("whep_stop")
    return Response(status_code=204)


@router.get("/{stream_id}/{asset_path:path}")
async def live_playback_asset(
    stream_id: str,
    asset_path: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    try:
        stream = live_service.get_playable_stream(db, stream_id)
        stream_token = live_service.authorize_playback(
            stream,
            token,
            _bearer(request),
            current_user,
            origin_or_referer=_origin(request),
        )
        path, safe = live_service.resolve_asset(stream, asset_path)
    except AppError as e:
        raise_app_error(e)

    archive_seg = path.parent.name == "archive" and safe.endswith(".ts")
    headers = cache_headers(live=not archive_seg, asset_name=safe)

    if safe.endswith(".m3u8"):
        _inc_playback("playlist")
        return await _playlist_response(
            path,
            stream_token,
            token,
            request,
            inject_edge=False,
        )

    media_type = "video/MP2T" if safe.endswith(".ts") else "application/octet-stream"
    if safe.endswith(".m4s"):
        media_type = "video/iso.segment"
    if safe.endswith(".mp4"):
        media_type = "video/mp4"
    if safe.endswith(".jpg") or safe.endswith(".jpeg"):
        media_type = "image/jpeg"
    if safe.endswith(".vtt"):
        media_type = "text/vtt"

    def iterfile():
        with open(path, mode="rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                yield chunk

    _inc_playback(
        "segment" if safe.endswith(".ts") or safe.endswith(".m4s") else "asset"
    )
    return StreamingResponse(iterfile(), media_type=media_type, headers=headers)
