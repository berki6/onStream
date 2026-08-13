from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base, VideoStatus


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(String(12), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)
    file_path = Column(String(500), nullable=False)
    hls_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    storyboard_path = Column(String(500), nullable=True)
    storyboard_vtt_path = Column(String(500), nullable=True)
    caption_vtt_path = Column(String(500), nullable=True)
    transcript_path = Column(String(500), nullable=True)
    detected_language = Column(String(16), nullable=True)
    chapters_json = Column(Text, nullable=True)
    suggested_title = Column(String(200), nullable=True)
    suggested_tags = Column(Text, nullable=True)
    moderation_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    moderation_labels = Column(Text, nullable=True)
    quarantined_at = Column(DateTime(timezone=True), nullable=True)
    preview_clip_path = Column(String(500), nullable=True)
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, index=True)
    is_public = Column(Boolean, default=False)
    visibility = Column(String(16), nullable=False, default="private")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="videos")
    views = relationship("VideoView", back_populates="video")
    embeddings = relationship(
        "VideoEmbedding", back_populates="video", cascade="all, delete-orphan"
    )
    watch_progress = relationship(
        "VideoWatchProgress", back_populates="video", cascade="all, delete-orphan"
    )
    share_links = relationship(
        "ShareLink", back_populates="video", cascade="all, delete-orphan"
    )
    favorites = relationship(
        "VideoFavorite", back_populates="video", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_videos_user_status", "user_id", "status"),)

    def __repr__(self):
        return f"<Video(title='{self.title}', id={self.id})>"


class VideoView(Base):
    __tablename__ = "video_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())
    watch_time = Column(Float, nullable=True)
    device_info = Column(String(200), nullable=True)

    viewer = relationship("User", back_populates="video_views")
    video = relationship("Video", back_populates="views")

    __table_args__ = (Index("idx_views_video_date", "video_id", "viewed_at"),)


class VideoEmbedding(Base):
    __tablename__ = "video_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=True)
    end_ms = Column(Integer, nullable=True)
    text = Column(Text, nullable=True)
    embedding = Column(Text, nullable=False)

    video = relationship("Video", back_populates="embeddings")

    __table_args__ = (
        Index("idx_video_embeddings_video_chunk", "video_id", "chunk_index"),
    )
