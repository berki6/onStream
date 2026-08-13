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

    # Storage: local | s3 | minio | r2
    STORAGE_BACKEND: str = os.environ.get("STORAGE_BACKEND", "local")
    S3_ENDPOINT_URL: str = os.environ.get("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY: str = os.environ.get("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.environ.get("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "onstream")
    S3_REGION: str = os.environ.get("S3_REGION", "us-east-1")
    # path | virtual — r2/minio default to path via registry when unset
    S3_ADDRESSING_STYLE: str = os.environ.get("S3_ADDRESSING_STYLE", "")

    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

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
    # CDN / edge host for playback URLs (purge + public links). Empty → PUBLIC_API_BASE_URL
    PUBLIC_PLAYBACK_BASE_URL: str = os.environ.get("PUBLIC_PLAYBACK_BASE_URL", "")

    # Email (password reset, etc.)
    EMAIL_PROVIDER: str = os.environ.get("EMAIL_PROVIDER", "log")
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER: str = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.environ.get("SMTP_FROM", "noreply@onstream.local")
    SMTP_USE_TLS: bool = _env_bool("SMTP_USE_TLS", "true")

    # Live streaming (MediaMTX RTMP → HLS)
    LIVE_ENABLED: bool = _env_bool("LIVE_ENABLED", "true")
    MEDIAMTX_RTMP_URL: str = os.environ.get(
        "MEDIAMTX_RTMP_URL", "rtmp://localhost:1935/live"
    )
    MEDIAMTX_HLS_URL: str = os.environ.get("MEDIAMTX_HLS_URL", "http://localhost:8888")
    LIVE_HLS_DIR: Path = PROJECT_ROOT / os.environ.get("LIVE_HLS_DIR", "data/live")
    LIVE_ABR_ENABLED: bool = _env_bool("LIVE_ABR_ENABLED", "false")
    LIVE_ABR_LADDER: str = os.environ.get("LIVE_ABR_LADDER", "360:800,720:2500,1080:5000")
    LIVE_NORMALIZE_ENABLED: bool = _env_bool("LIVE_NORMALIZE_ENABLED", "true")
    LIVE_NORMALIZE_POLL_ATTEMPTS: int = int(
        os.environ.get("LIVE_NORMALIZE_POLL_ATTEMPTS", "20")
    )
    LIVE_NORMALIZE_POLL_INTERVAL: float = float(
        os.environ.get("LIVE_NORMALIZE_POLL_INTERVAL", "0.4")
    )
    # Live HLS only (VOD keeps HLS_SEGMENT_SECONDS=4). 1s is the Expo-safe floor.
    LIVE_HLS_SEGMENT_SECONDS: int = int(
        os.environ.get("LIVE_HLS_SEGMENT_SECONDS", "1")
    )
    MEDIAMTX_RTSP_URL: str = os.environ.get(
        "MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554"
    )
    MEDIAMTX_AUTH_SECRET: str = os.environ.get("MEDIAMTX_AUTH_SECRET", "")
    PUBLIC_RTMP_BASE_URL: str = os.environ.get(
        "PUBLIC_RTMP_BASE_URL", "rtmp://localhost:1935/live"
    )
    LIVE_HEALTH_ENABLED: bool = _env_bool("LIVE_HEALTH_ENABLED", "true")
    LIVE_STALE_SECONDS: int = int(os.environ.get("LIVE_STALE_SECONDS", "20"))
    PLAYBACK_CDN_HEADERS_ENABLED: bool = _env_bool(
        "PLAYBACK_CDN_HEADERS_ENABLED", "true"
    )
    MEDIAMTX_API_URL: str = os.environ.get(
        "MEDIAMTX_API_URL", "http://localhost:9997"
    )
    MEDIAMTX_API_USER: str = os.environ.get("MEDIAMTX_API_USER", "")
    MEDIAMTX_API_PASS: str = os.environ.get("MEDIAMTX_API_PASS", "")
    OTEL_ENABLED: bool = _env_bool("OTEL_ENABLED", "false")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", ""
    )
    MEDIA_PYAV_ENABLED: bool = _env_bool("MEDIA_PYAV_ENABLED", "true")
    QOE_CANARY_ENABLED: bool = _env_bool("QOE_CANARY_ENABLED", "true")

    # WebRTC / WHIP-WHEP
    PUBLIC_WEBRTC_BASE_URL: str = os.environ.get(
        "PUBLIC_WEBRTC_BASE_URL", "http://localhost:8889"
    )
    PUBLIC_HTTPS_BASE_URL: str = os.environ.get("PUBLIC_HTTPS_BASE_URL", "")

    # CDN purge
    CDN_PROVIDER: str = os.environ.get("CDN_PROVIDER", "none")
    CLOUDFLARE_API_TOKEN: str = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    CLOUDFLARE_ZONE_ID: str = os.environ.get("CLOUDFLARE_ZONE_ID", "")
    BUNNY_API_KEY: str = os.environ.get("BUNNY_API_KEY", "")
    BUNNY_PULL_ZONE_ID: str = os.environ.get("BUNNY_PULL_ZONE_ID", "")

    # Encode / quality
    FFMPEG_HWACCEL: str = os.environ.get("FFMPEG_HWACCEL", "")
    QUALITY_GATE_ENABLED: bool = _env_bool("QUALITY_GATE_ENABLED", "false")
    QUALITY_GATE_STRICT: bool = _env_bool("QUALITY_GATE_STRICT", "false")
    QUALITY_GATE_MIN_VMAF: float = float(os.environ.get("QUALITY_GATE_MIN_VMAF", "70"))

    # Demo player
    DEMO_PLAYER_ENABLED: bool = _env_bool("DEMO_PLAYER_ENABLED", "false")

    # AI media intelligence (off by default for CI)
    AI_ENABLED: bool = _env_bool("AI_ENABLED", "false")
    AI_CAPTIONS_ENABLED: bool = _env_bool("AI_CAPTIONS_ENABLED", "true")
    AI_CHAPTERS_ENABLED: bool = _env_bool("AI_CHAPTERS_ENABLED", "true")
    AI_MODERATION_ENABLED: bool = _env_bool("AI_MODERATION_ENABLED", "true")
    AI_EMBEDDINGS_ENABLED: bool = _env_bool("AI_EMBEDDINGS_ENABLED", "true")
    AI_SMART_THUMBNAIL_ENABLED: bool = _env_bool("AI_SMART_THUMBNAIL_ENABLED", "true")
    WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "tiny")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    AI_MODERATION_THRESHOLD: float = float(
        os.environ.get("AI_MODERATION_THRESHOLD", "0.7")
    )
    AI_CAPTIONS_PROVIDER: str = os.environ.get("AI_CAPTIONS_PROVIDER", "faster_whisper")
    AI_EMBEDDINGS_PROVIDER: str = os.environ.get(
        "AI_EMBEDDINGS_PROVIDER", "sentence_transformers"
    )
    AI_MODERATION_PROVIDER: str = os.environ.get("AI_MODERATION_PROVIDER", "heuristic")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def public_playback_base_url(self) -> str:
        base = (self.PUBLIC_PLAYBACK_BASE_URL or self.PUBLIC_API_BASE_URL or "").rstrip(
            "/"
        )
        return base or "http://localhost:8000"

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
    def live_abr_ladder_list(self) -> List[dict]:
        """Parse LIVE_ABR_LADDER into [{height, bitrate_k}]."""
        rungs = []
        for part in self.LIVE_ABR_LADDER.split(","):
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
            if self.EMAIL_PROVIDER in {"none", "log"}:
                raise RuntimeError(
                    "EMAIL_PROVIDER must be 'smtp' in production "
                    "(none/log would drop or log password-reset secrets)."
                )
            if self.EMAIL_PROVIDER == "smtp" and not (self.SMTP_HOST or "").strip():
                raise RuntimeError(
                    "SMTP_HOST is required when EMAIL_PROVIDER=smtp in production."
                )
            if self.STORAGE_BACKEND in {"s3", "minio", "r2"}:
                if not (self.S3_BUCKET or "").strip():
                    raise RuntimeError(
                        "S3_BUCKET is required for object storage in production."
                    )
            if self.STORAGE_BACKEND in {"minio", "r2"} and not (
                self.S3_ENDPOINT_URL or ""
            ).strip():
                raise RuntimeError(
                    "S3_ENDPOINT_URL is required for minio/r2 in production."
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

    @field_validator("STORAGE_BACKEND")
    @classmethod
    def validate_storage_backend(cls, v: str) -> str:
        key = (v or "").lower().strip()
        allowed = {"local", "s3", "minio", "r2"}
        if key not in allowed:
            raise ValueError(
                "STORAGE_BACKEND must be 'local', 's3', 'minio', or 'r2'"
            )
        return key

    @field_validator("S3_ADDRESSING_STYLE")
    @classmethod
    def validate_s3_addressing_style(cls, v: str) -> str:
        if not v or not str(v).strip():
            return ""
        allowed = {"path", "virtual"}
        key = str(v).lower().strip()
        if key not in allowed:
            raise ValueError("S3_ADDRESSING_STYLE must be 'path' or 'virtual'")
        return key

    @field_validator("SMTP_PORT")
    @classmethod
    def validate_smtp_port(cls, v: int) -> int:
        if not (1 <= int(v) <= 65535):
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        return int(v)

    @field_validator("CDN_PROVIDER")
    @classmethod
    def validate_cdn_provider(cls, v: str) -> str:
        allowed = {"none", "cloudflare", "bunny"}
        if v.lower() not in allowed:
            raise ValueError("CDN_PROVIDER must be 'none', 'cloudflare', or 'bunny'")
        return v.lower()

    @field_validator("EMAIL_PROVIDER")
    @classmethod
    def validate_email_provider(cls, v: str) -> str:
        allowed = {"none", "log", "smtp"}
        if v.lower() not in allowed:
            raise ValueError("EMAIL_PROVIDER must be 'none', 'log', or 'smtp'")
        return v.lower()

    @field_validator("AI_CAPTIONS_PROVIDER")
    @classmethod
    def validate_ai_captions_provider(cls, v: str) -> str:
        allowed = {"mock", "faster_whisper"}
        if v.lower() not in allowed:
            raise ValueError(
                "AI_CAPTIONS_PROVIDER must be 'mock' or 'faster_whisper'"
            )
        return v.lower()

    @field_validator("AI_EMBEDDINGS_PROVIDER")
    @classmethod
    def validate_ai_embeddings_provider(cls, v: str) -> str:
        allowed = {"mock", "sentence_transformers"}
        if v.lower() not in allowed:
            raise ValueError(
                "AI_EMBEDDINGS_PROVIDER must be 'mock' or 'sentence_transformers'"
            )
        return v.lower()

    @field_validator("AI_MODERATION_PROVIDER")
    @classmethod
    def validate_ai_moderation_provider(cls, v: str) -> str:
        allowed = {"heuristic"}
        if v.lower() not in allowed:
            raise ValueError("AI_MODERATION_PROVIDER must be 'heuristic'")
        return v.lower()


settings = Settings()