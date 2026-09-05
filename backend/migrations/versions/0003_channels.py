"""add channels table and scope users by channel

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05
"""
import json
import os

import sqlalchemy as sa
from alembic import op

from app.crypto import encrypt

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _backfill_users_channel(connection: sa.engine.Connection) -> None:
    """Creates a 'legacy-telegram' channel from TELEGRAM_BOT_TOKEN (if set)
    and backfills every existing users row onto it. Raises if there are
    existing users but no token to migrate them onto. Pulled out of
    `upgrade()` as a plain function (taking any SQLAlchemy Connection, not
    specifically an Alembic migration context) so it's unit-testable against
    an in-memory SQLite engine without invoking the Alembic CLI at all —
    see `tests/test_migration_0003_backfill.py`.
    """
    user_count = connection.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if user_count and not bot_token:
        raise RuntimeError(
            "users table has existing rows but TELEGRAM_BOT_TOKEN is not set — "
            "set it before running this migration so existing users can be "
            "attached to a migrated 'legacy-telegram' channel."
        )

    if not bot_token:
        return

    credentials = encrypt(json.dumps({"bot_token": bot_token}))
    connection.execute(
        sa.text(
            "INSERT INTO channels "
            "(key, display_name, channel_type, encrypted_credentials, is_active, created_at) "
            "VALUES (:key, :display_name, :channel_type, :credentials, 1, CURRENT_TIMESTAMP)"
        ),
        {
            "key": "legacy-telegram",
            "display_name": "Telegram (migrated)",
            "channel_type": "telegram",
            "credentials": credentials,
        },
    )
    legacy_channel_id = connection.execute(
        sa.text("SELECT id FROM channels WHERE key = 'legacy-telegram'")
    ).scalar()
    connection.execute(sa.text("UPDATE users SET channel_id = :cid"), {"cid": legacy_channel_id})


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("encrypted_credentials", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))

    _backfill_users_channel(op.get_bind())

    op.drop_index("ix_users_telegram_user_id", table_name="users")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("channel_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("fk_users_channel_id", "channels", ["channel_id"], ["id"])

    op.create_index(
        "ix_users_channel_id_telegram_user_id", "users", ["channel_id", "telegram_user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_channel_id_telegram_user_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_channel_id", type_="foreignkey")
        batch_op.drop_column("channel_id")
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)
    op.drop_table("channels")
