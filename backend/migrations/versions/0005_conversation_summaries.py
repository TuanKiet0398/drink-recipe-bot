"""add conversation_summaries table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("summary_text", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "last_summarized_message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conversation_summaries")
