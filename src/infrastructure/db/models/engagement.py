"""Watch progress, share links, and favorites models."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class VideoWatchProgress(Base):
    __tablename__ = "video_watch_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    position_seconds = Column(Float, nullable=False, default=0.0)
    duration_seconds = Column(Float, nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    # Dismiss from Continue shelf without wiping watch history.
    hidden_from_continue = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_watched_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="watch_progress")
    video = relationship("Video", back_populates="watch_progress")

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_watch_progress_user_video"),
        Index("idx_watch_progress_user_last", "user_id", "last_watched_at"),
    )


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(16), unique=True, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    label = Column(String(120), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    max_views = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    clip_start_seconds = Column(Float, nullable=True)
    clip_end_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="share_links")
    creator = relationship("User", back_populates="share_links")

    __table_args__ = (Index("idx_share_links_video", "video_id"),)


class VideoFavorite(Base):
    __tablename__ = "video_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="favorites")
    video = relationship("Video", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_favorite_user_video"),
        Index("idx_favorites_user_created", "user_id", "created_at"),
    )
