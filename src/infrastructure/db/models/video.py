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
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, index=True)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="videos")
    views = relationship("VideoView", back_populates="video")

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
