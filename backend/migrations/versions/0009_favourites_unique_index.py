"""dedupe favourites and add unique index + updated_at

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "favourites",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE favourites SET updated_at = created_at WHERE updated_at IS NULL")
    # Keep only the earliest row per (user_id, drink_name) before the unique
    # index is added, so pre-existing duplicates (no dedupe before this
    # migration) don't block the constraint.
    op.execute(
        """
        DELETE FROM favourites
        WHERE id NOT IN (
            SELECT MIN(id) FROM favourites GROUP BY user_id, drink_name
        )
        """
    )
    op.create_index(
        "ix_favourites_user_id_drink_name",
        "favourites",
        ["user_id", "drink_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_favourites_user_id_drink_name", table_name="favourites")
    op.drop_column("favourites", "updated_at")
