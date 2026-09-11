"""add accounts table for web registration

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_accounts_username", table_name="accounts")
    op.drop_table("accounts")
