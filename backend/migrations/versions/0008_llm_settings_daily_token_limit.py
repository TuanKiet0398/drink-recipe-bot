"""add llm_settings.daily_token_limit

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_settings", sa.Column("daily_token_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_settings", "daily_token_limit")
