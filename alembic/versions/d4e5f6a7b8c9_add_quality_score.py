"""Add quality_score column to videos for VMAF/PSNR gate.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("videos", "quality_score"):
        op.add_column(
            "videos",
            sa.Column("quality_score", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("videos", "quality_score"):
        op.drop_column("videos", "quality_score")
