"""Named playback windows on a VOD — no re-encode."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class VideoHighlight(Base):
    __tablename__ = "video_highlights"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(16), unique=True, nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    title = Column(String(120), nullable=False)
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="highlights")
    creator = relationship("User", back_populates="highlights")

    __table_args__ = (
        UniqueConstraint(
            "video_id", "start_seconds", "end_seconds", name="uq_highlight_window"
        ),
        Index("idx_highlights_video_created", "video_id", "created_at"),
    )
