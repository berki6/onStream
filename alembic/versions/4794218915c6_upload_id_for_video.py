"""upload_id_for_video

Revision ID: 4794218915c6
Revises: 353315e7c3a7
Create Date: 2025-11-10 20:29:53.487088
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String


# revision identifiers, used by Alembic.
revision = "4794218915c6"
down_revision = "353315e7c3a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column as nullable using batch operation (works with SQLite)
    with op.batch_alter_table("videos") as batch_op:
        batch_op.add_column(sa.Column("upload_id", sa.String(length=12), nullable=True))

    # Populate existing rows with unique placeholder values
    videos = table(
        "videos", column("id", sa.Integer), column("upload_id", sa.String(length=12))
    )

    connection = op.get_bind()
    result = connection.execute(sa.select(videos.c.id))

    for row in result:
        # Generate a dummy upload_id based on the id, adjust logic as needed
        upload_id_value = f"UPL{row.id:09d}"  # like UPL000000001
        connection.execute(
            videos.update()
            .where(videos.c.id == row.id)
            .values(upload_id=upload_id_value)
        )

    # Alter column to be non-nullable using batch operation
    with op.batch_alter_table("videos") as batch_op:
        batch_op.alter_column("upload_id", nullable=False)

    # Create a unique index on upload_id
    op.create_index(op.f("ix_videos_upload_id"), "videos", ["upload_id"], unique=True)


def downgrade() -> None:
    # Drop the unique index and column in downgrade
    op.drop_index(op.f("ix_videos_upload_id"), table_name="videos")
    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_column("upload_id")
