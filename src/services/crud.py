from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.schema import models, schemas

logger = get_logger(__name__)


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    from src.core.auth import get_password_hash

    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Created user: {user.username}")
    return db_user


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_videos_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Video)
        .filter(models.Video.user_id == user_id)
        .filter(models.Video.status != models.VideoStatus.DELETED)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_video(db: Session, video: schemas.VideoCreate, user_id: int):
    from src.utils.upload_id import generate_unique_upload_id

    # Generate unique upload_id
    upload_id = generate_unique_upload_id(db)

    db_video = models.Video(**video.model_dump(), user_id=user_id, upload_id=upload_id)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    logger.info(
        f"Created video: upload_id '{db_video.upload_id}', title '{video.title}' for user ID {user_id}"
    )
    return db_video


def get_video(db: Session, video_id: int):
    return db.query(models.Video).filter(models.Video.id == video_id).first()


def get_video_by_upload_id(db: Session, upload_id: str):
    return (
        db.query(models.Video)
        .filter(models.Video.upload_id == upload_id)
        .filter(models.Video.status != models.VideoStatus.DELETED)
        .first()
    )


def delete_video_by_upload_id(db: Session, upload_id: str):
    video = db.query(models.Video).filter(models.Video.upload_id == upload_id).first()
    if video:
        video.status = models.VideoStatus.DELETED
        db.commit()
        logger.info(f"Soft deleted video upload_id {upload_id}")
    return video


def create_video_job(db: Session, job: schemas.VideoJobCreate):
    db_job = models.VideoJob(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Created video job for upload_id {job.upload_id}")
    return db_job


def get_job_for_video(db: Session, video: models.Video):
    return (
        db.query(models.VideoJob)
        .filter(models.VideoJob.upload_id == video.upload_id)
        .first()
    )


# Playlist CRUD functions
def create_playlist(db: Session, playlist: schemas.PlaylistCreate, user_id: int):
    db_playlist = models.Playlist(**playlist.model_dump(), user_id=user_id)
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    logger.info(f"Created playlist: '{db_playlist.name}' for user ID {user_id}")
    return db_playlist


def get_playlists_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_playlist(db: Session, playlist_id: int):
    return db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()


def delete_playlist(db: Session, playlist_id: int):
    playlist = (
        db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    )
    if playlist:
        db.delete(playlist)
        db.commit()
        logger.info(f"Deleted playlist ID {playlist_id}")
    return playlist


def add_video_to_playlist(
    db: Session, playlist_id: int, video_id: int, position: int = 0
):
    # Check if video is already in playlist
    existing = (
        db.query(models.PlaylistVideo)
        .filter(
            models.PlaylistVideo.playlist_id == playlist_id,
            models.PlaylistVideo.video_id == video_id,
        )
        .first()
    )
    if existing:
        return None  # Video already in playlist

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


def remove_video_from_playlist(db: Session, playlist_id: int, video_id: int):
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


def get_playlist_videos(db: Session, playlist_id: int):
    return (
        db.query(models.PlaylistVideo)
        .filter(models.PlaylistVideo.playlist_id == playlist_id)
        .order_by(models.PlaylistVideo.position)
        .all()
    )


def update_video_position_in_playlist(
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
