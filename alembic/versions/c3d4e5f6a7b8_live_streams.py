"""Add live_streams table for OBS/VLC RTMP publishing.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("live_streams"):
        return

    op.create_table(
        "live_streams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("stream_key_hash", sa.String(length=64), nullable=False),
        sa.Column("stream_key_prefix", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("hls_path", sa.String(length=500), nullable=True),
        sa.Column("abr_hls_path", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_id"),
        sa.UniqueConstraint("stream_key_hash"),
    )
    op.create_index(
        op.f("ix_live_streams_id"), "live_streams", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_live_streams_stream_id"),
        "live_streams",
        ["stream_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_live_streams_user_id"), "live_streams", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_live_streams_stream_key_hash"),
        "live_streams",
        ["stream_key_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_live_streams_status"), "live_streams", ["status"], unique=False
    )
    op.create_index(
        "idx_live_streams_user_status",
        "live_streams",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    if not _has_table("live_streams"):
        return
    op.drop_index("idx_live_streams_user_status", table_name="live_streams")
    op.drop_index(op.f("ix_live_streams_status"), table_name="live_streams")
    op.drop_index(op.f("ix_live_streams_stream_key_hash"), table_name="live_streams")
    op.drop_index(op.f("ix_live_streams_user_id"), table_name="live_streams")
    op.drop_index(op.f("ix_live_streams_stream_id"), table_name="live_streams")
    op.drop_index(op.f("ix_live_streams_id"), table_name="live_streams")
    op.drop_table("live_streams")
