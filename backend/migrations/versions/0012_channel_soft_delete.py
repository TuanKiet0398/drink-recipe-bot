"""add channels.deleted_at and channels.token_hash

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("channels", sa.Column("token_hash", sa.String(), nullable=True))
    op.create_index("ix_channels_token_hash", "channels", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_channels_token_hash", table_name="channels")
    op.drop_column("channels", "token_hash")
    op.drop_column("channels", "deleted_at")
