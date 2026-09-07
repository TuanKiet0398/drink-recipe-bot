"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_user_id", sa.String, unique=True, index=True, nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "favourites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("drink_name", sa.String, nullable=False),
        sa.Column("confidence", sa.String, nullable=False, server_default="inferred"),
        sa.Column("source", sa.String, nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("target", sa.String, nullable=False, server_default=""),
        sa.Column("ip", sa.String, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("documents")
    op.drop_table("favourites")
    op.drop_table("messages")
    op.drop_table("users")
