"""Add error_code to video_jobs and queued_jobs.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("video_jobs", "error_code"):
        op.add_column(
            "video_jobs",
            sa.Column("error_code", sa.String(64), nullable=True),
        )
    if not _has_column("queued_jobs", "error_code"):
        op.add_column(
            "queued_jobs",
            sa.Column("error_code", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    if _has_column("queued_jobs", "error_code"):
        op.drop_column("queued_jobs", "error_code")
    if _has_column("video_jobs", "error_code"):
        op.drop_column("video_jobs", "error_code")
