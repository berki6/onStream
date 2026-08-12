"""Add watch progress, share links, favorites, and Postgres FTS.

Revision ID: g7a8b9c0d1e2
Revises: f6a7b8c9d0e1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "g7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
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
    if not _has_table("video_watch_progress"):
        op.create_table(
            "video_watch_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=False
            ),
            sa.Column("position_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column(
                "completed", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "last_watched_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "user_id", "video_id", name="uq_watch_progress_user_video"
            ),
        )
        op.create_index(
            "ix_video_watch_progress_user_id", "video_watch_progress", ["user_id"]
        )
        op.create_index(
            "ix_video_watch_progress_video_id", "video_watch_progress", ["video_id"]
        )
        op.create_index(
            "idx_watch_progress_user_last",
            "video_watch_progress",
            ["user_id", "last_watched_at"],
        )

    if not _has_table("share_links"):
        op.create_table(
            "share_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=16), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=False
            ),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_views", sa.Integer(), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("public_id", name="uq_share_links_public_id"),
        )
        op.create_index("ix_share_links_public_id", "share_links", ["public_id"])
        op.create_index("ix_share_links_video_id", "share_links", ["video_id"])
        op.create_index(
            "ix_share_links_created_by_user_id", "share_links", ["created_by_user_id"]
        )
        op.create_index("idx_share_links_video", "share_links", ["video_id"])

    if not _has_table("video_favorites"):
        op.create_table(
            "video_favorites",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=False
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("user_id", "video_id", name="uq_favorite_user_video"),
        )
        op.create_index("ix_video_favorites_user_id", "video_favorites", ["user_id"])
        op.create_index("ix_video_favorites_video_id", "video_favorites", ["video_id"])
        op.create_index(
            "idx_favorites_user_created", "video_favorites", ["user_id", "created_at"]
        )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if not _has_column("videos", "search_vector"):
            op.execute(
                """
                ALTER TABLE videos ADD COLUMN search_vector tsvector
                GENERATED ALWAYS AS (
                    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
                    setweight(to_tsvector('english', coalesce(suggested_title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(suggested_tags, '')), 'C')
                ) STORED
                """
            )
        if not _has_index("videos", "idx_videos_search_vector"):
            op.execute(
                "CREATE INDEX idx_videos_search_vector ON videos USING GIN (search_vector)"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if _has_index("videos", "idx_videos_search_vector"):
            op.drop_index("idx_videos_search_vector", table_name="videos")
        if _has_column("videos", "search_vector"):
            op.drop_column("videos", "search_vector")

    if _has_table("video_favorites"):
        op.drop_table("video_favorites")
    if _has_table("share_links"):
        op.drop_table("share_links")
    if _has_table("video_watch_progress"):
        op.drop_table("video_watch_progress")
