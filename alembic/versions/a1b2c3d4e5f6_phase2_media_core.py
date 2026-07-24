"""Phase 2: job stages, storyboard paths, uploads, webhooks, API keys.

Idempotent for DBs that already received these columns/tables via create_all.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9a985310ce4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    indexes = inspect(bind).get_indexes(table)
    return any(ix.get("name") == index_name for ix in indexes)


def upgrade() -> None:
    if not _has_column("videos", "storyboard_path"):
        op.add_column(
            "videos", sa.Column("storyboard_path", sa.String(length=500), nullable=True)
        )
    if not _has_column("videos", "storyboard_vtt_path"):
        op.add_column(
            "videos",
            sa.Column("storyboard_vtt_path", sa.String(length=500), nullable=True),
        )

    if not _has_column("video_jobs", "stage"):
        op.add_column(
            "video_jobs",
            sa.Column(
                "stage", sa.String(length=32), server_default="queued", nullable=True
            ),
        )
    if not _has_column("video_jobs", "cancel_requested"):
        op.add_column(
            "video_jobs",
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=True,
            ),
        )
    if not _has_index("video_jobs", "ix_video_jobs_stage"):
        op.create_index("ix_video_jobs_stage", "video_jobs", ["stage"])

    if not _has_table("upload_sessions"):
        op.create_table(
            "upload_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("upload_id", sa.String(length=12), nullable=False),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=True
            ),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("storage_key", sa.String(length=500), nullable=False),
            sa.Column("bytes_received", sa.BigInteger(), nullable=True),
            sa.Column("content_type", sa.String(length=100), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_upload_sessions_upload_id", "upload_sessions", ["upload_id"]
        )
        op.create_index("ix_upload_sessions_user_id", "upload_sessions", ["user_id"])
        op.create_index("ix_upload_sessions_status", "upload_sessions", ["status"])

    if not _has_table("webhook_endpoints"):
        op.create_table(
            "webhook_endpoints",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("secret", sa.String(length=128), nullable=False),
            sa.Column("events", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_webhook_endpoints_user_id", "webhook_endpoints", ["user_id"]
        )

    if not _has_table("webhook_deliveries"):
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "endpoint_id",
                sa.Integer(),
                sa.ForeignKey("webhook_endpoints.id"),
                nullable=False,
            ),
            sa.Column("event", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"]
        )
        op.create_index("ix_webhook_deliveries_event", "webhook_deliveries", ["event"])
        op.create_index(
            "ix_webhook_deliveries_status", "webhook_deliveries", ["status"]
        )

    if not _has_table("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("key_prefix", sa.String(length=12), nullable=False),
            sa.Column("key_hash", sa.String(length=128), nullable=False),
            sa.Column("scopes", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
        op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
        op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    if not _has_table("idempotency_records"):
        op.create_table(
            "idempotency_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("key", sa.String(length=128), nullable=False),
            sa.Column("request_path", sa.String(length=255), nullable=False),
            sa.Column("response_code", sa.Integer(), nullable=False),
            sa.Column("response_body", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "uq_idempotency_user_key",
            "idempotency_records",
            ["user_id", "key"],
            unique=True,
        )


def downgrade() -> None:
    if _has_table("idempotency_records"):
        op.drop_table("idempotency_records")
    if _has_table("api_keys"):
        op.drop_table("api_keys")
    if _has_table("webhook_deliveries"):
        op.drop_table("webhook_deliveries")
    if _has_table("webhook_endpoints"):
        op.drop_table("webhook_endpoints")
    if _has_table("upload_sessions"):
        op.drop_table("upload_sessions")
    if _has_index("video_jobs", "ix_video_jobs_stage"):
        op.drop_index("ix_video_jobs_stage", table_name="video_jobs")
    if _has_column("video_jobs", "cancel_requested"):
        op.drop_column("video_jobs", "cancel_requested")
    if _has_column("video_jobs", "stage"):
        op.drop_column("video_jobs", "stage")
    if _has_column("videos", "storyboard_vtt_path"):
        op.drop_column("videos", "storyboard_vtt_path")
    if _has_column("videos", "storyboard_path"):
        op.drop_column("videos", "storyboard_path")
