"""Link live streams to archived VOD rows.

Revision ID: j0a1b2c3d4e5
Revises: i9c0d1e2f3a4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "j0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "i9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("live_streams", "archived_upload_id"):
        op.add_column(
            "live_streams",
            sa.Column("archived_upload_id", sa.String(length=12), nullable=True),
        )
    if not _has_column("videos", "source"):
        op.add_column(
            "videos",
            sa.Column(
                "source",
                sa.String(length=16),
                nullable=False,
                server_default="upload",
            ),
        )
    if not _has_column("videos", "live_stream_id"):
        op.add_column(
            "videos",
            sa.Column("live_stream_id", sa.String(length=12), nullable=True),
        )
        op.create_index(
            "ix_videos_live_stream_id",
            "videos",
            ["live_stream_id"],
            unique=True,
        )


def downgrade() -> None:
    if _has_column("videos", "live_stream_id"):
        op.drop_index("ix_videos_live_stream_id", table_name="videos")
        op.drop_column("videos", "live_stream_id")
    if _has_column("videos", "source"):
        op.drop_column("videos", "source")
    if _has_column("live_streams", "archived_upload_id"):
        op.drop_column("live_streams", "archived_upload_id")
