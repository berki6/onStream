import os
from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils.paths import PROJECT_ROOT


def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).lower() in ("true", "1", "yes")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    ENV: str = os.environ.get("ENV", "development")

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.environ.get("LOG_FILE", "python.log")
    PROMETHEUS_ENABLED: bool = _env_bool("PROMETHEUS_ENABLED", "true")

    # Default remains SQLite for local/tests; Docker Compose sets Postgres
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./onstream.db")
    ANALYTICS_ENABLED: bool = _env_bool("ANALYTICS_ENABLED", "false")
    DEBUG: bool = _env_bool("DEBUG", "false")
    INTERNAL_API_KEY: str = os.environ.get("INTERNAL_API_KEY", "")

    MAX_UPLOAD_SIZE: int = int(
        os.environ.get("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024))
    )
    MAX_VIDEO_DURATION_SECONDS: int = int(
        os.environ.get("MAX_VIDEO_DURATION_SECONDS", "3600")
    )
    MAX_TITLE_LENGTH: int = int(os.environ.get("MAX_TITLE_LENGTH", "200"))
    MAX_LIST_LIMIT: int = int(os.environ.get("MAX_LIST_LIMIT", "100"))
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

    # Storage: local | s3
    STORAGE_BACKEND: str = os.environ.get("STORAGE_BACKEND", "local")
    S3_ENDPOINT_URL: str = os.environ.get("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY: str = os.environ.get("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.environ.get("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "onstream")
    S3_REGION: str = os.environ.get("S3_REGION", "us-east-1")

    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
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
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "14")
    )
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(
        os.environ.get("PASSWORD_RESET_EXPIRE_MINUTES", "30")
    )

    # Comma-separated origins; empty = allow all in non-production only
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "")

    AUTH_RATE_LIMIT_PER_MINUTE: int = int(
        os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "20")
    )

    # Phase 2 media core
    STREAM_TOKEN_EXPIRE_SECONDS: int = int(
        os.environ.get("STREAM_TOKEN_EXPIRE_SECONDS", "3600")
    )
    STREAM_ALLOWED_ORIGINS: str = os.environ.get("STREAM_ALLOWED_ORIGINS", "")
    HLS_SEGMENT_SECONDS: int = int(os.environ.get("HLS_SEGMENT_SECONDS", "4"))
    UPLOAD_SESSION_EXPIRE_MINUTES: int = int(
        os.environ.get("UPLOAD_SESSION_EXPIRE_MINUTES", "120")
    )
    IDEMPOTENCY_TTL_HOURS: int = int(os.environ.get("IDEMPOTENCY_TTL_HOURS", "24"))
    # heights:bitrates_kbps pairs, comma-separated e.g. 360:800,480:1400,720:2800,1080:5000
    ABR_LADDER: str = os.environ.get(
        "ABR_LADDER", "360:800,480:1400,720:2800,1080:5000"
    )
    PUBLIC_API_BASE_URL: str = os.environ.get(
        "PUBLIC_API_BASE_URL", "http://localhost:8000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def abr_ladder_list(self) -> List[dict]:
        """Parse ABR_LADDER into [{height, bitrate_k}]."""
        rungs = []
        for part in self.ABR_LADDER.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            height_s, br_s = part.split(":", 1)
            rungs.append({"height": int(height_s), "bitrate_k": int(br_s)})
        return rungs

    @property
    def stream_allowed_origins_list(self) -> List[str]:
        if not self.STREAM_ALLOWED_ORIGINS.strip():
            return []
        return [o.strip() for o in self.STREAM_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS.strip():
            if self.ENV == "production":
                return []
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_settings(self):
        if self.ENV == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == "dev-secret-change-me":
                raise RuntimeError(
                    "SECRET_KEY is not set for production; set SECRET_KEY env var."
                )
            if not self.CORS_ORIGINS.strip():
                raise RuntimeError(
                    "CORS_ORIGINS must be set explicitly in production."
                )
        return self

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        allowed = (
            "sqlite://",
            "postgresql://",
            "postgresql+psycopg2://",
            "postgresql+psycopg://",
            "mysql://",
            "mysql+pymysql://",
        )
        if not any(v.startswith(prefix) for prefix in allowed):
            raise ValueError(
                "DATABASE_URL must start with sqlite://, postgresql://, or mysql://"
            )
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v:
            raise ValueError("REDIS_URL cannot be empty")
        if not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://'")
        return v

    @field_validator("CELERY_BROKER_URL")
    @classmethod
    def validate_celery_broker_url(cls, v: str) -> str:
        if not v:
            raise ValueError("CELERY_BROKER_URL cannot be empty")
        if not (
            v.startswith("redis://")
            or v.startswith("rediss://")
            or v.startswith("amqp://")
        ):
            raise ValueError(
                "CELERY_BROKER_URL must start with 'redis://', 'rediss://', or 'amqp://'"
            )
        return v

    @field_validator("STORAGE_BACKEND")
    @classmethod
    def validate_storage_backend(cls, v: str) -> str:
        allowed = {"local", "s3"}
        if v.lower() not in allowed:
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'")
        return v.lower()


settings = Settings()
