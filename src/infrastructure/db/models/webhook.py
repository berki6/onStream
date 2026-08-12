from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.db.base import Base


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    secret = Column(String(128), nullable=False)
    events = Column(Text, nullable=False)  # comma-separated event names
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="webhook_endpoints")
    deliveries = relationship(
        "WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan"
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    endpoint_id = Column(
        Integer, ForeignKey("webhook_endpoints.id"), nullable=False, index=True
    )
    event = Column(String(64), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default="pending", index=True)  # pending, success, failed
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
