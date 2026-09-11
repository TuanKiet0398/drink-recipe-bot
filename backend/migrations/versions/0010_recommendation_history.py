"""add recommendation_history table

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recommendation_history_user_id_product_name",
        "recommendation_history",
        ["user_id", "product_name"],
        unique=True,
    )
    op.create_index("ix_recommendation_history_user_id", "recommendation_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_history_user_id", table_name="recommendation_history")
    op.drop_index("ix_recommendation_history_user_id_product_name", table_name="recommendation_history")
    op.drop_table("recommendation_history")
