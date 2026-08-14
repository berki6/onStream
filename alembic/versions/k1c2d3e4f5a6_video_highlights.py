"""Named VOD highlight windows (clip catalog).

Revision ID: k1c2d3e4f5a6
Revises: j0a1b2c3d4e5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "k1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "j0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("video_highlights"):
        return
    op.create_table(
        "video_highlights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "video_id", "start_seconds", "end_seconds", name="uq_highlight_window"
        ),
    )
    op.create_index("ix_video_highlights_public_id", "video_highlights", ["public_id"])
    op.create_index("ix_video_highlights_video_id", "video_highlights", ["video_id"])
    op.create_index(
        "idx_highlights_video_created",
        "video_highlights",
        ["video_id", "created_at"],
    )


def downgrade() -> None:
    if not _has_table("video_highlights"):
        return
    op.drop_index("idx_highlights_video_created", table_name="video_highlights")
    op.drop_index("ix_video_highlights_video_id", table_name="video_highlights")
    op.drop_index("ix_video_highlights_public_id", table_name="video_highlights")
    op.drop_table("video_highlights")
