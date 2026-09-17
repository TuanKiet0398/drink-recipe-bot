"""add accounts.role

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("role", sa.String(), nullable=False, server_default="customer"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "role")
