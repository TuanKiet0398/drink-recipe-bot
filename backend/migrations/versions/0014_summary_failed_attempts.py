"""add conversation_summaries.failed_attempts

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_summaries",
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("conversation_summaries", "failed_attempts")
