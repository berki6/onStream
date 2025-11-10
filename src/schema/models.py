from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum,
    Text,
    Boolean,
    Float,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from enum import Enum as PyEnum

Base = declarative_base()


class VideoStatus(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    ERROR = "ERROR"
    DELETED = "DELETED"  # Soft delete


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)  # For bcrypt
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")
    playlists = relationship(
        "Playlist", back_populates="owner", cascade="all, delete-orphan"
    )
    video_views = relationship("VideoView", back_populates="viewer")

    def __repr__(self):
        return f"<User(username='{self.username}', id={self.id})>"


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(
        String(12), unique=True, nullable=False, index=True
    )  # Alphanumeric public ID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)  # In seconds, from ffprobe
    file_path = Column(String(500), nullable=False)  # e.g., /storage/originals/{id}.mp4
    hls_path = Column(String(500), nullable=True)  # e.g., /streams/{id}/playlist.m3u8
    thumbnail_path = Column(String(500), nullable=True)  # e.g., /thumbs/{id}.jpg
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, index=True)
    is_public = Column(Boolean, default=False)  # For sharing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="videos")
    views = relationship("VideoView", back_populates="video")

    # Indexes
    __table_args__ = (Index("idx_videos_user_status", "user_id", "status"),)

    def __repr__(self):
        return f"<Video(title='{self.title}', id={self.id})>"


class VideoView(Base):  # For analytics (nice-to-have)
    __tablename__ = "video_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # NULL for anonymous
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())
    watch_time = Column(Float, nullable=True)  # Seconds watched
    device_info = Column(String(200), nullable=True)  # Optional: IP, user-agent snippet

    # Relationships
    viewer = relationship("User", back_populates="video_views")
    video = relationship("Video", back_populates="views")

    __table_args__ = (Index("idx_views_video_date", "video_id", "viewed_at"),)

    def __repr__(self):
        return f"<VideoView(video_id={self.video_id}, id={self.id})>"


class Playlist(Base):  # Nice-to-have
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="playlists")
    videos = relationship(
        "PlaylistVideo", back_populates="playlist", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Playlist(name='{self.name}', id={self.id})>"


class PlaylistVideo(Base):  # Junction table for many-to-many
    __tablename__ = "playlist_videos"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(
        Integer, ForeignKey("playlists.id"), nullable=False, index=True
    )
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)  # Order in playlist

    # Relationships
    playlist = relationship("Playlist", back_populates="videos")
    video = relationship("Video")

    __table_args__ = (
        Index("uq_playlist_video", "playlist_id", "video_id", unique=True),
    )

    def __repr__(self):
        return (
            f"<PlaylistVideo(playlist_id={self.playlist_id}, video_id={self.video_id})>"
        )


class VideoJob(Base):
    __tablename__ = "video_jobs"

    upload_id = Column(String(12), primary_key=True)  # Matches video upload ID
    status = Column(
        String, default="processing"
    )  # statuses: uploading, transcoding, thumbnail, ready, error
    progress = Column(Integer, default=0)  # percent complete (0-100)
    eta = Column(Integer, default=0)  # estimated seconds remaining
    message = Column(Text, nullable=True)  # logs or error messages
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<VideoJob(upload_id='{self.upload_id}', status='{self.status}', progress={self.progress}%)>"
