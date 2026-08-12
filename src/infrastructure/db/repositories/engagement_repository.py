"""Repositories for watch progress, share links, and favorites."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus


# --- Watch progress ---


def get_progress(
    db: Session, user_id: int, video_id: int
) -> Optional[models.VideoWatchProgress]:
    return (
        db.query(models.VideoWatchProgress)
        .filter(
            models.VideoWatchProgress.user_id == user_id,
            models.VideoWatchProgress.video_id == video_id,
        )
        .first()
    )


def upsert_progress(
    db: Session,
    user_id: int,
    video_id: int,
    position_seconds: float,
    duration_seconds: Optional[float],
    completed: bool,
) -> models.VideoWatchProgress:
    row = get_progress(db, user_id, video_id)
    now = datetime.now(timezone.utc)
    if row is None:
        row = models.VideoWatchProgress(
            user_id=user_id,
            video_id=video_id,
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
            completed=completed,
            hidden_from_continue=False,
            last_watched_at=now,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
            row = get_progress(db, user_id, video_id)
            if row is None:
                raise
    row.position_seconds = position_seconds
    if duration_seconds is not None:
        row.duration_seconds = duration_seconds
    row.completed = completed
    # Watching again restores the item on Continue.
    row.hidden_from_continue = False
    row.last_watched_at = now
    db.commit()
    db.refresh(row)
    return row


def dismiss_from_continue(db: Session, user_id: int, video_id: int) -> bool:
    row = get_progress(db, user_id, video_id)
    if not row:
        return False
    row.hidden_from_continue = True
    db.commit()
    return True


def delete_progress(db: Session, user_id: int, video_id: int) -> bool:
    row = get_progress(db, user_id, video_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def clear_progress(db: Session, user_id: int) -> int:
    deleted = (
        db.query(models.VideoWatchProgress)
        .filter(models.VideoWatchProgress.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def clear_continue(db: Session, user_id: int) -> int:
    """Hide in-progress rows from Continue; keep them in History."""
    updated = (
        db.query(models.VideoWatchProgress)
        .filter(models.VideoWatchProgress.user_id == user_id)
        .filter(models.VideoWatchProgress.completed.is_(False))
        .filter(models.VideoWatchProgress.hidden_from_continue.is_(False))
        .update(
            {models.VideoWatchProgress.hidden_from_continue: True},
            synchronize_session=False,
        )
    )
    db.commit()
    return int(updated or 0)


def list_continue(
    db: Session, user_id: int, limit: int = 20
) -> List[Tuple[models.VideoWatchProgress, models.Video]]:
    return (
        db.query(models.VideoWatchProgress, models.Video)
        .join(models.Video, models.Video.id == models.VideoWatchProgress.video_id)
        .filter(models.VideoWatchProgress.user_id == user_id)
        .filter(models.VideoWatchProgress.completed.is_(False))
        .filter(models.VideoWatchProgress.hidden_from_continue.is_(False))
        .filter(models.VideoWatchProgress.position_seconds > 5)
        .filter(models.Video.status == VideoStatus.READY)
        .filter(models.Video.user_id == user_id)
        .order_by(models.VideoWatchProgress.last_watched_at.desc())
        .limit(limit)
        .all()
    )


def list_history(
    db: Session, user_id: int, limit: int = 50
) -> List[Tuple[models.VideoWatchProgress, models.Video]]:
    return (
        db.query(models.VideoWatchProgress, models.Video)
        .join(models.Video, models.Video.id == models.VideoWatchProgress.video_id)
        .filter(models.VideoWatchProgress.user_id == user_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .filter(models.Video.user_id == user_id)
        .order_by(models.VideoWatchProgress.last_watched_at.desc())
        .limit(limit)
        .all()
    )


# --- Share links ---


def get_share_by_public_id(
    db: Session, public_id: str
) -> Optional[models.ShareLink]:
    return (
        db.query(models.ShareLink)
        .filter(models.ShareLink.public_id == public_id)
        .first()
    )


def create_share(db: Session, link: models.ShareLink) -> models.ShareLink:
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_shares_for_video(
    db: Session, video_id: int, user_id: int
) -> List[models.ShareLink]:
    return (
        db.query(models.ShareLink)
        .filter(
            models.ShareLink.video_id == video_id,
            models.ShareLink.created_by_user_id == user_id,
        )
        .order_by(models.ShareLink.created_at.desc())
        .all()
    )


def list_shares_for_user(db: Session, user_id: int) -> List[models.ShareLink]:
    return (
        db.query(models.ShareLink)
        .filter(models.ShareLink.created_by_user_id == user_id)
        .order_by(models.ShareLink.created_at.desc())
        .limit(100)
        .all()
    )


def save_share(db: Session, link: models.ShareLink) -> models.ShareLink:
    db.commit()
    db.refresh(link)
    return link


def try_increment_share_view(
    db: Session, share_id: int, *, now: Optional[datetime] = None
) -> Optional[models.ShareLink]:
    """
    Atomically increment view_count when the link is still active and under
    max_views. Returns the updated row, or None if the increment was rejected.
    """
    now = now or datetime.now(timezone.utc)
    # Dialect-portable conditional update (Postgres + SQLite).
    result = db.execute(
        text(
            """
            UPDATE share_links
            SET view_count = view_count + 1
            WHERE id = :id
              AND revoked_at IS NULL
              AND expires_at > :now
              AND (max_views IS NULL OR view_count < max_views)
            """
        ),
        {"id": share_id, "now": now},
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return db.query(models.ShareLink).filter(models.ShareLink.id == share_id).first()


# --- Favorites ---


def get_favorite(
    db: Session, user_id: int, video_id: int
) -> Optional[models.VideoFavorite]:
    return (
        db.query(models.VideoFavorite)
        .filter(
            models.VideoFavorite.user_id == user_id,
            models.VideoFavorite.video_id == video_id,
        )
        .first()
    )


def add_favorite(db: Session, user_id: int, video_id: int) -> models.VideoFavorite:
    existing = get_favorite(db, user_id, video_id)
    if existing:
        return existing
    row = models.VideoFavorite(user_id=user_id, video_id=video_id)
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        existing = get_favorite(db, user_id, video_id)
        if existing:
            return existing
        raise


def remove_favorite(db: Session, user_id: int, video_id: int) -> bool:
    row = get_favorite(db, user_id, video_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def clear_favorites(db: Session, user_id: int) -> int:
    deleted = (
        db.query(models.VideoFavorite)
        .filter(models.VideoFavorite.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def list_favorites(
    db: Session, user_id: int, limit: int = 50
) -> List[Tuple[models.VideoFavorite, models.Video]]:
    return (
        db.query(models.VideoFavorite, models.Video)
        .join(models.Video, models.Video.id == models.VideoFavorite.video_id)
        .filter(models.VideoFavorite.user_id == user_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .order_by(models.VideoFavorite.created_at.desc())
        .limit(limit)
        .all()
    )


def search_keyword_ranked(
    db: Session,
    user_id: int,
    query: str,
    limit: int = 20,
) -> List[Tuple[models.Video, float]]:
    """Postgres FTS when available; ILIKE fallback otherwise."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        # search_vector is a generated column; query via text for dialect safety.
        sql = text(
            """
            SELECT v.id, ts_rank_cd(v.search_vector, websearch_to_tsquery('english', :q)) AS rank
            FROM videos v
            WHERE v.user_id = :uid
              AND v.status != 'DELETED'
              AND v.search_vector @@ websearch_to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :lim
            """
        )
        rows = db.execute(
            sql, {"q": query, "uid": user_id, "lim": limit}
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        rank_map = {r[0]: float(r[1] or 0.0) for r in rows}
        videos = (
            db.query(models.Video)
            .filter(models.Video.id.in_(ids))
            .all()
        )
        by_id = {v.id: v for v in videos}
        return [(by_id[i], rank_map[i]) for i in ids if i in by_id]

    like = f"%{query}%"
    videos = (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .filter(models.Video.status != VideoStatus.DELETED)
        .filter(
            (models.Video.title.ilike(like))
            | (models.Video.description.ilike(like))
            | (models.Video.suggested_title.ilike(like))
            | (models.Video.suggested_tags.ilike(like))
        )
        .limit(limit)
        .all()
    )
    return [(v, 1.0) for v in videos]
