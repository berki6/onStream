from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")
    playlists = relationship(
        "Playlist", back_populates="owner", cascade="all, delete-orphan"
    )
    video_views = relationship("VideoView", back_populates="viewer")
    webhook_endpoints = relationship(
        "WebhookEndpoint", back_populates="owner", cascade="all, delete-orphan"
    )
    api_keys = relationship(
        "ApiKey", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(username='{self.username}', id={self.id})>"
