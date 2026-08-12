"""Add hidden_from_continue on watch progress.

Revision ID: h8b9c0d1e2f3
Revises: g7a8b9c0d1e2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "h8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "g7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("video_watch_progress", "hidden_from_continue"):
        op.add_column(
            "video_watch_progress",
            sa.Column(
                "hidden_from_continue",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    if _has_column("video_watch_progress", "hidden_from_continue"):
        op.drop_column("video_watch_progress", "hidden_from_continue")
