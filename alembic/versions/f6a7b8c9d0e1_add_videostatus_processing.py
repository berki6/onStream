"""Add PROCESSING to videostatus enum (used by transcode worker).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Native enum from initial_schema lacked PROCESSING; Python model has had it.
    op.execute("ALTER TYPE videostatus ADD VALUE IF NOT EXISTS 'PROCESSING'")


def downgrade() -> None:
    # Postgres cannot easily remove enum values; leave as no-op.
    pass
