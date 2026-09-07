"""add llm_settings table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No seed row on purpose: with the table empty the application falls back
    # to OPENAI_API_KEY from the environment, so deploying this changes no
    # behaviour and no secret passes through a migration.
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("encrypted_api_key", sa.String(), nullable=True),
        sa.Column("chat_model", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False, server_default=""),
        sa.CheckConstraint("id = 1", name="ck_llm_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("llm_settings")
