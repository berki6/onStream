"""Live stream model for OBS/VLC RTMP → HLS publishing."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class LiveStream(Base):
    __tablename__ = "live_streams"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(String(12), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    stream_key_hash = Column(String(64), unique=True, nullable=False, index=True)
    stream_key_prefix = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="idle", index=True)
    is_public = Column(Boolean, default=False, nullable=False)
    hls_path = Column(String(500), nullable=True)
    abr_hls_path = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    archived_upload_id = Column(String(12), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="live_streams")

    __table_args__ = (
        Index("idx_live_streams_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<LiveStream(stream_id='{self.stream_id}', status='{self.status}')>"
