"""Add video visibility and share-link clip windows.

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "i9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "h8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("videos", "visibility"):
        op.add_column(
            "videos",
            sa.Column(
                "visibility",
                sa.String(length=16),
                nullable=False,
                server_default="private",
            ),
        )
        bind = op.get_bind()
        bind.execute(
            text("UPDATE videos SET visibility = 'public' WHERE is_public = true")
        )
        bind.execute(
            text("UPDATE videos SET visibility = 'private' WHERE is_public = false")
        )

    if not _has_column("share_links", "clip_start_seconds"):
        op.add_column(
            "share_links",
            sa.Column("clip_start_seconds", sa.Float(), nullable=True),
        )
    if not _has_column("share_links", "clip_end_seconds"):
        op.add_column(
            "share_links",
            sa.Column("clip_end_seconds", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("share_links", "clip_end_seconds"):
        op.drop_column("share_links", "clip_end_seconds")
    if _has_column("share_links", "clip_start_seconds"):
        op.drop_column("share_links", "clip_start_seconds")
    if _has_column("videos", "visibility"):
        op.drop_column("videos", "visibility")
