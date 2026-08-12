from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base, UploadSessionStatus


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(String(36), primary_key=True)  # UUID
    upload_id = Column(String(12), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    status = Column(
        String(20), default=UploadSessionStatus.PENDING.value, index=True
    )
    storage_key = Column(String(500), nullable=False)
    bytes_received = Column(BigInteger, default=0)
    content_type = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
