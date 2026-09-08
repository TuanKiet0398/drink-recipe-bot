"""add customer_notes table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False, server_default="inferred"),
        sa.Column("source", sa.String(), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_customer_notes_user_id_note_type",
        "customer_notes",
        ["user_id", "note_type"],
        unique=True,
    )
    op.create_index("ix_customer_notes_user_id", "customer_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_notes_user_id", table_name="customer_notes")
    op.drop_index("ix_customer_notes_user_id_note_type", table_name="customer_notes")
    op.drop_table("customer_notes")
