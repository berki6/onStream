from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="playlists")
    videos = relationship(
        "PlaylistVideo", back_populates="playlist", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Playlist(name='{self.name}', id={self.id})>"


class PlaylistVideo(Base):
    __tablename__ = "playlist_videos"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(
        Integer, ForeignKey("playlists.id"), nullable=False, index=True
    )
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)

    playlist = relationship("Playlist", back_populates="videos")
    video = relationship("Video")

    __table_args__ = (
        Index("uq_playlist_video", "playlist_id", "video_id", unique=True),
    )

    def __repr__(self):
        return (
            f"<PlaylistVideo(playlist_id={self.playlist_id}, video_id={self.video_id})>"
        )
