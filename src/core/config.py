import os

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

from src.utils.paths import PROJECT_ROOT


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Keep defaults conservative for local development. Celery settings are
    populated so tasks/workers can run with minimal additional configuration.
    """

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ENV: str = os.environ.get("ENV", "development")

    # Observability / runtime
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.environ.get("LOG_FILE", "python.log")
    PROMETHEUS_ENABLED: bool = os.environ.get("PROMETHEUS_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # Runtime DB URL (kept in sync with src/db/database.py if you want to centralize)
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./onstream.db")
    ANALYTICS_ENABLED: bool = os.environ.get("ANALYTICS_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    # Internal API key for protecting sensitive endpoints (analytics, RAG admin)
    INTERNAL_API_KEY: str = os.environ.get("INTERNAL_API_KEY", "")

    # Max upload size used by upload endpoints (bytes)
    MAX_UPLOAD_SIZE: int = int(
        os.environ.get("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024))
    )
    # Max video duration in seconds
    MAX_VIDEO_DURATION_SECONDS: int = int(
        os.environ.get("MAX_VIDEO_DURATION_SECONDS", "3600")
    )
    # Max title length for videos
    MAX_TITLE_LENGTH: int = int(os.environ.get("MAX_TITLE_LENGTH", "200"))
    # Max limit for list endpoints
    MAX_LIST_LIMIT: int = int(os.environ.get("MAX_LIST_LIMIT", "100"))
    # Thumbnail dimensions
    THUMBNAIL_WIDTH: int = int(os.environ.get("THUMBNAIL_WIDTH", "320"))
    THUMBNAIL_HEIGHT: int = int(os.environ.get("THUMBNAIL_HEIGHT", "180"))
    VIDEO_STORAGE_DIR: str = os.environ.get("VIDEO_STORAGE_DIR", "data/videos")
    VIDEO_UPLOAD_DIR: Path = PROJECT_ROOT / os.environ.get(
        "VIDEO_UPLOAD_DIR", "data/uploads"
    )
    VIDEO_HLS_DIR: Path = PROJECT_ROOT / os.environ.get("VIDEO_HLS_DIR", "data/hls")
    VIDEO_THUMBNAIL_DIR: Path = PROJECT_ROOT / os.environ.get(
        "VIDEO_THUMBNAIL_DIR", "data/thumbnails"
    )

    # Optional Sentry DSN for error monitoring
    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
    # Redis URL for caching and task queues
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    # Celery / worker settings
    CELERY_BROKER_URL: str = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    CELERY_RESULT_BACKEND: str = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )
    CELERY_DEFAULT_QUEUE: str = os.environ.get("CELERY_DEFAULT_QUEUE", "default")
    CELERY_ENABLED: bool = bool(int(os.environ.get("CELERY_ENABLED", "0")))

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown vars instead of error
    )

    @model_validator(mode="after")
    def _validate_settings(self):
        """Validate critical settings and fail fast for unsafe production configs."""
        if self.ENV == "production":
            if not self.SECRET_KEY:
                raise RuntimeError(
                    "SECRET_KEY is not set for production; set SECRET_KEY env var."
                )
        return self

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        if not (
            v.startswith("sqlite://")
            or v.startswith("postgresql://")
            or v.startswith("mysql://")
        ):
            raise ValueError(
                "DATABASE_URL must start with 'sqlite://', 'postgresql://', or 'mysql://'"
            )
        return v

    # Optional: Add for other URLs if needed
    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v:
            raise ValueError("REDIS_URL cannot be empty")
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must start with 'redis://'")
        return v

    @field_validator("CELERY_BROKER_URL")
    @classmethod
    def validate_celery_broker_url(cls, v: str) -> str:
        if not v:
            raise ValueError("CELERY_BROKER_URL cannot be empty")
        if not (v.startswith("redis://") or v.startswith("amqp://")):
            raise ValueError(
                "CELERY_BROKER_URL must start with 'redis://' or 'amqp://'"
            )
        return v


settings = Settings()
