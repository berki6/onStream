from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.infrastructure.db import models
from src import schemas

logger = get_logger(__name__)


def create(db: Session, playlist: schemas.PlaylistCreate, user_id: int):
    db_playlist = models.Playlist(**playlist.model_dump(), user_id=user_id)
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    logger.info(f"Created playlist: '{db_playlist.name}' for user ID {user_id}")
    return db_playlist


def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    total_count = (
        db.query(models.Playlist).filter(models.Playlist.user_id == user_id).count()
    )
    playlists = (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return playlists, total_count


def get_by_id(db: Session, playlist_id: int):
    return db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()


def delete(db: Session, playlist_id: int):
    playlist = (
        db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    )
    if playlist:
        db.delete(playlist)
        db.commit()
        logger.info(f"Deleted playlist ID {playlist_id}")
    return playlist


def add_video(db: Session, playlist_id: int, video_id: int, position: int = 0):
    existing = (
        db.query(models.PlaylistVideo)
        .filter(
            models.PlaylistVideo.playlist_id == playlist_id,
            models.PlaylistVideo.video_id == video_id,
        )
        .first()
    )
    if existing:
        return None

    db_playlist_video = models.PlaylistVideo(
        playlist_id=playlist_id, video_id=video_id, position=position
    )
    db.add(db_playlist_video)
    db.commit()
    db.refresh(db_playlist_video)
    logger.info(
        f"Added video ID {video_id} to playlist ID {playlist_id} at position {position}"
    )
    return db_playlist_video


def remove_video(db: Session, playlist_id: int, video_id: int):
    playlist_video = (
        db.query(models.PlaylistVideo)
        .filter(
            models.PlaylistVideo.playlist_id == playlist_id,
            models.PlaylistVideo.video_id == video_id,
        )
        .first()
    )
    if playlist_video:
        db.delete(playlist_video)
        db.commit()
        logger.info(f"Removed video ID {video_id} from playlist ID {playlist_id}")
    return playlist_video


def playlist_ids_containing_video(
    db: Session, user_id: int, video_id: int
) -> set:
    rows = (
        db.query(models.PlaylistVideo.playlist_id)
        .join(
            models.Playlist,
            models.Playlist.id == models.PlaylistVideo.playlist_id,
        )
        .filter(
            models.Playlist.user_id == user_id,
            models.PlaylistVideo.video_id == video_id,
        )
        .all()
    )
    return {row[0] for row in rows}


def get_videos(db: Session, playlist_id: int):
    return (
        db.query(models.PlaylistVideo)
        .filter(models.PlaylistVideo.playlist_id == playlist_id)
        .order_by(models.PlaylistVideo.position)
        .all()
    )


def update_video_position(
    db: Session, playlist_id: int, video_id: int, position: int
):
    playlist_video = (
        db.query(models.PlaylistVideo)
        .filter(
            models.PlaylistVideo.playlist_id == playlist_id,
            models.PlaylistVideo.video_id == video_id,
        )
        .first()
    )
    if playlist_video:
        playlist_video.position = position
        db.commit()
        db.refresh(playlist_video)
        logger.info(
            f"Updated position of video ID {video_id} in playlist ID {playlist_id} to {position}"
        )
    return playlist_video
