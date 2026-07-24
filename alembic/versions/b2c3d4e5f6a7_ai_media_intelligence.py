"""AI media intelligence columns, job_type, and video_embeddings.

Idempotent for DBs that already received these columns/tables via create_all.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
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
    video_cols = [
        ("caption_vtt_path", sa.String(length=500)),
        ("transcript_path", sa.String(length=500)),
        ("detected_language", sa.String(length=16)),
        ("chapters_json", sa.Text()),
        ("suggested_title", sa.String(length=200)),
        ("suggested_tags", sa.Text()),
        ("moderation_score", sa.Float()),
        ("moderation_labels", sa.Text()),
        ("quarantined_at", sa.DateTime(timezone=True)),
        ("preview_clip_path", sa.String(length=500)),
    ]
    for name, col_type in video_cols:
        if not _has_column("videos", name):
            op.add_column("videos", sa.Column(name, col_type, nullable=True))

    # Best-effort add QUARANTINED to native Postgres enum if present
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.execute(
                "ALTER TYPE videostatus ADD VALUE IF NOT EXISTS 'QUARANTINED'"
            )
        except Exception:
            pass

    if not _has_column("queued_jobs", "job_type"):
        op.add_column(
            "queued_jobs",
            sa.Column(
                "job_type",
                sa.String(length=32),
                server_default="transcode",
                nullable=False,
            ),
        )
    if not _has_index("queued_jobs", "ix_queued_jobs_job_type"):
        op.create_index("ix_queued_jobs_job_type", "queued_jobs", ["job_type"])
    if not _has_index("queued_jobs", "idx_queued_jobs_upload_type"):
        op.create_index(
            "idx_queued_jobs_upload_type",
            "queued_jobs",
            ["upload_id", "job_type", "status"],
        )

    if not _has_table("video_embeddings"):
        op.create_table(
            "video_embeddings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "video_id",
                sa.Integer(),
                sa.ForeignKey("videos.id"),
                nullable=False,
            ),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("start_ms", sa.Integer(), nullable=True),
            sa.Column("end_ms", sa.Integer(), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("embedding", sa.Text(), nullable=False),
        )
        op.create_index(
            "ix_video_embeddings_video_id", "video_embeddings", ["video_id"]
        )
        op.create_index(
            "idx_video_embeddings_video_chunk",
            "video_embeddings",
            ["video_id", "chunk_index"],
        )


def downgrade() -> None:
    if _has_table("video_embeddings"):
        op.drop_table("video_embeddings")
    if _has_index("queued_jobs", "idx_queued_jobs_upload_type"):
        op.drop_index("idx_queued_jobs_upload_type", table_name="queued_jobs")
    if _has_index("queued_jobs", "ix_queued_jobs_job_type"):
        op.drop_index("ix_queued_jobs_job_type", table_name="queued_jobs")
    if _has_column("queued_jobs", "job_type"):
        op.drop_column("queued_jobs", "job_type")

    for name in (
        "preview_clip_path",
        "quarantined_at",
        "moderation_labels",
        "moderation_score",
        "suggested_tags",
        "suggested_title",
        "chapters_json",
        "detected_language",
        "transcript_path",
        "caption_vtt_path",
    ):
        if _has_column("videos", name):
            op.drop_column("videos", name)
