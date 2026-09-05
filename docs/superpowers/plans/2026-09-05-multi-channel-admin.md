# Multi-channel Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `TELEGRAM_BOT_TOKEN` with an admin-managed `channels` table (multiple instances, AES-GCM-encrypted credentials), a `ChannelManager` that starts/stops Telegram long-poll tasks dynamically as channels are created/edited/deleted, a new `/admin/channels` CRUD API, and a new "Channels" tab in the admin frontend.

**Architecture:** `channels` (new table, multi-instance, encrypted credentials) drives a process-wide `ChannelManager` that keeps one `asyncio.Task` per active Telegram channel in sync with the DB. `app/telegram_client.py` and `app/telegram_poller.py` are reworked to take a `bot_token`/`channel_id` per call instead of reading a single global setting. `users` gains a `channel_id` so the same Telegram user id can exist independently under two different bots. Alembic is wired up for real (previously an unused dependency) to safely backfill the existing `users` table.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, `cryptography` (AES-GCM), React 19 + react-router-dom v6 + Tailwind (frontend), pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-multi-channel-admin-design.md`

## Global Constraints

- Multiple instances per channel type are allowed (e.g. two Telegram bots running concurrently) — `users` is scoped by `(channel_id, telegram_user_id)`, not `telegram_user_id` alone.
- Only `channel_type == "telegram"` is functional; the admin API rejects any other value on create. The frontend's channel-type selector shows other types as disabled ("coming soon").
- Credentials are encrypted at rest (AES-GCM via a new `ENCRYPTION_KEY` env var) and never returned decrypted by the admin API after creation.
- Alembic is wired up for real: a baseline migration capturing the current schema, then a migration adding `channels` + backfilling `users.channel_id` from the existing `TELEGRAM_BOT_TOKEN` env var.
- The `/webhook/telegram` HTTP route and `_verify_telegram_secret` are removed — this project already runs on Telegram long-polling; the route is dead code that also bakes in the single-global-token assumption this plan removes.
- Every command below that touches the real `backend/local.db` or runs `alembic`/`pytest` must run with `python3.11` (not plain `python3`) — this project's actual runtime dependencies (`chromadb`, `alembic`, etc.) are installed for `python3.11` only, confirmed earlier in this project's history.

---

## Task 1: Wire up Alembic (baseline migration)

**Files:**
- Create: `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_baseline.py` (via `alembic init` + `alembic revision --autogenerate`)
- Modify: `backend/alembic.ini` (only if `alembic init` doesn't already point `script_location` at `migrations` — it already does, so likely no edit needed; verify)

**Interfaces:**
- Produces: a working `alembic` CLI (`alembic current`, `alembic upgrade head`, `alembic revision --autogenerate`) targeting `Settings.database_url`, with `backend/local.db` stamped at the baseline revision. Task 3 adds the next migration on top of this.

- [ ] **Step 1: Initialize the Alembic environment**

Run (from `backend/`): `python3.11 -m alembic init migrations`

This creates `migrations/env.py`, `migrations/script.py.mako`, and an empty `migrations/versions/` directory. `alembic.ini` already exists with `script_location = migrations`, so this step should not need to touch it — if `alembic init` complains the directory exists, that's fine, just proceed to configure `env.py`.

- [ ] **Step 2: Point `env.py` at this project's models and settings**

Replace the generated `backend/migrations/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401 - registers all tables on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Generate the baseline migration against an empty database**

The real `backend/local.db` already has all these tables (created ad hoc before Alembic existed). To generate a baseline migration that can also create these tables from scratch on a fresh install, temporarily generate against a non-existent database file, then restore the real one:

```bash
cd backend
mv local.db local.db.bak
python3.11 -m alembic revision --autogenerate -m "baseline"
mv local.db.bak local.db
```

This produces `migrations/versions/0001_baseline_<hash>.py` (or similarly-named) containing `op.create_table(...)` for `users`, `messages`, `favourites`, `documents`, `admin_audit_log`, `token_usage`. Open it and confirm it has real `create_table` calls in `upgrade()` (not an empty migration) — if it's empty, `local.db.bak` wasn't actually moved aside before running the command; redo Step 3.

- [ ] **Step 4: Stamp the existing database as already at the baseline**

The real `local.db` already has this exact schema, so mark it as up to date without re-running the `CREATE TABLE` statements:

```bash
python3.11 -m alembic stamp head
```

- [ ] **Step 5: Verify**

```bash
python3.11 -m alembic current
```

Expected: prints the baseline revision id, matching the file in `migrations/versions/`.

```bash
python3.11 - <<'EOF'
import sqlite3
conn = sqlite3.connect("local.db")
print(conn.execute("SELECT COUNT(*) FROM users").fetchone())
print(conn.execute("SELECT COUNT(*) FROM messages").fetchone())
EOF
```

Expected: the same row counts as before this task (existing data untouched — this task only records history, it runs no DDL against the real database).

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/migrations backend/alembic.ini
git commit -m "chore(backend): wire up Alembic with a baseline migration"
```

(`backend/local.db` stays untracked/gitignored — only the migration scripts are committed.)

---

## Task 2: Credential encryption (`app/crypto.py`)

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `backend/.env`
- Create: `backend/app/crypto.py`
- Test: `backend/tests/test_crypto.py` (new)

**Interfaces:**
- Consumes: `Settings.encryption_key`.
- Produces: `encrypt(plaintext: str) -> str`, `decrypt(ciphertext: str) -> str` — consumed by Task 3's migration and Task 7's `admin_channels.py`/`ChannelManager`.

- [ ] **Step 1: Add the `cryptography` dependency**

In `backend/pyproject.toml`, add to `[project].dependencies`:

```toml
    "cryptography>=42",
```

Run: `pip install -e /mnt/d/Workspace/MLOPS_project/backend` (uses the `python3.11`-targeted `pip` already confirmed earlier in this project).

- [ ] **Step 2: Add `encryption_key` to `Settings` and generate a real key**

In `backend/app/config.py`, add a field:

```python
    encryption_key: str = ""
```

Generate a real key and add it to `backend/.env` (gitignored, so this is safe to run for real):

```bash
cd backend
python3.11 -c "import secrets, base64; print('ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())" >> .env
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_crypto.py`:

```python
import base64
import secrets

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto import decrypt, encrypt


@pytest.fixture(autouse=True)
def _fake_encryption_key(monkeypatch):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from app import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_encrypt_decrypt_round_trip():
    ciphertext = encrypt("my-secret-bot-token")
    assert ciphertext != "my-secret-bot-token"
    assert decrypt(ciphertext) == "my-secret-bot-token"


def test_encrypt_produces_different_ciphertext_each_time():
    # Random nonce per call -> same plaintext never produces identical
    # ciphertext, so two channels with the same token don't leak that fact.
    assert encrypt("same-token") != encrypt("same-token")


def test_decrypt_rejects_tampered_ciphertext():
    ciphertext = encrypt("my-secret-bot-token")
    tail = "AAAA" if not ciphertext.endswith("AAAA") else "BBBB"
    tampered = ciphertext[:-4] + tail
    with pytest.raises(InvalidTag):
        decrypt(tampered)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && python3.11 -m pytest tests/test_crypto.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.crypto'`.

- [ ] **Step 5: Write `app/crypto.py`**

```python
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

_NONCE_SIZE = 12


def _aesgcm() -> AESGCM:
    settings = get_settings()
    key = base64.b64decode(settings.encryption_key)
    return AESGCM(key)


def encrypt(plaintext: str) -> str:
    aesgcm = _aesgcm()
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(ciphertext: str) -> str:
    aesgcm = _aesgcm()
    raw = base64.b64decode(ciphertext)
    nonce, encrypted = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_crypto.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/pyproject.toml backend/app/config.py backend/app/crypto.py backend/tests/test_crypto.py
git commit -m "feat(backend): add AES-GCM credential encryption (app/crypto.py)"
```

(`backend/.env`'s new `ENCRYPTION_KEY` line stays untracked — it's gitignored.)

---

## Task 3: `Channel` model, `users.channel_id`, and the backfill migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/migrations/versions/0002_channels.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_models.py`, `backend/tests/test_admin_logs.py`, `backend/tests/test_admin_users.py`, `backend/tests/test_agent_graph.py`, `backend/tests/test_agent_nodes.py` (every existing `User(telegram_user_id=...)` call site needs a `channel_id`)
- Test: `backend/tests/test_migration_0002_backfill.py` (new)

**Interfaces:**
- Produces: `Channel` model (`id, key, display_name, channel_type, encrypted_credentials, is_active, created_at`), `User.channel_id` FK, composite unique index `(channel_id, telegram_user_id)`. A `channel_id` pytest fixture in `conftest.py` — consumed by every test in this task and by Task 7's tests.

- [ ] **Step 1: Update `app/db/models.py`**

Add `Index` and `UniqueConstraint`... actually only `Index` is needed here. Change the top import line from:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
```

to:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
```

Replace the `User` class with:

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_channel_id_telegram_user_id", "channel_id", "telegram_user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    telegram_user_id: Mapped[str] = mapped_column(String)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    channel: Mapped["Channel"] = relationship(back_populates="users")
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    favourites: Mapped[list["Favourite"]] = relationship(back_populates="user")
```

Add a new `Channel` class right before `class User(Base):`:

```python
class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String)
    channel_type: Mapped[str] = mapped_column(String)
    encrypted_credentials: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="channel")
```

- [ ] **Step 2: Add a `channel_id` fixture and fix every existing `User(...)` call site**

In `backend/tests/conftest.py`, add (after the `db_session` fixture):

```python
@pytest.fixture()
def channel_id(db_session) -> int:
    from app.db.models import Channel

    channel = Channel(
        key="test-channel",
        display_name="Test Channel",
        channel_type="telegram",
        encrypted_credentials="test-encrypted-credentials",
        is_active=True,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel.id
```

In `backend/tests/test_models.py`, change:

```python
def test_create_user_with_related_rows(db_session):
    user = User(telegram_user_id="123")
```

to:

```python
def test_create_user_with_related_rows(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="123")
```

Add a new test to the same file confirming the new constraint:

```python
def test_users_unique_per_channel_and_telegram_id(db_session, channel_id):
    from app.db.models import Channel
    from sqlalchemy.exc import IntegrityError

    db_session.add(User(channel_id=channel_id, telegram_user_id="dup"))
    db_session.commit()

    other_channel = Channel(
        key="other-channel",
        display_name="Other",
        channel_type="telegram",
        encrypted_credentials="x",
    )
    db_session.add(other_channel)
    db_session.commit()
    db_session.refresh(other_channel)

    # Same telegram_user_id under a *different* channel is allowed.
    db_session.add(User(channel_id=other_channel.id, telegram_user_id="dup"))
    db_session.commit()

    # Same telegram_user_id under the *same* channel is not.
    db_session.add(User(channel_id=channel_id, telegram_user_id="dup"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

Add `import pytest` at the top of `test_models.py` if not already present.

In `backend/tests/test_admin_logs.py`, change `test_access_log_returns_messages(client, db_session):` to `test_access_log_returns_messages(client, db_session, channel_id):` and `User(telegram_user_id="3")` to `User(channel_id=channel_id, telegram_user_id="3")`.

In `backend/tests/test_admin_users.py`, add `channel_id` as a parameter to `test_list_users_returns_summary`, `test_block_and_unblock_user`, and `test_block_user_writes_audit_log`, and change their `User(telegram_user_id="N")` calls to `User(channel_id=channel_id, telegram_user_id="N")` (three call sites: `"1"`, `"2"`, `"4"`).

In `backend/tests/test_agent_graph.py`, add `channel_id` as a parameter to `test_run_agent_produces_a_reply` and change `User(telegram_user_id="55")` to `User(channel_id=channel_id, telegram_user_id="55")`.

In `backend/tests/test_agent_nodes.py`, add `channel_id` as a parameter to every test function that currently takes `db_session` and constructs a `User` (`test_fetch_history_loads_recent_messages_and_favourites`, `test_fetch_history_returns_last_n_messages_in_chronological_order`, `test_extract_favourite_upserts_when_preference_detected`, `test_extract_favourite_noop_when_no_preference`), and change their four `User(telegram_user_id="N")` calls (`"99"`, `"100"`, `"7"`, `"8"`) to `User(channel_id=channel_id, telegram_user_id="N")`.

- [ ] **Step 3: Run the full suite to confirm the model change is consistent**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3.11 -m pytest -q`
Expected: the tests touched above pass; other failures at this point (anything still constructing `User` without `channel_id`, or still referencing `get_qdrant_client`-style removed things from earlier work) should already be fixed by the edits above — if anything else fails with `IntegrityError: NOT NULL constraint failed: users.channel_id`, find and fix that remaining call site the same way before continuing.

- [ ] **Step 4: Write migration `0002_channels`**

Run: `cd backend && python3.11 -m alembic revision -m "add channels table and scope users by channel"` (plain `revision`, not `--autogenerate` — this migration's data backfill can't be autogenerated).

Replace the generated file's `upgrade()`/`downgrade()` (keep the autogenerated `revision`/`down_revision` header as-is) with:

```python
import json
import os

import sqlalchemy as sa
from alembic import op

from app.crypto import encrypt


def _backfill_users_channel(connection: sa.engine.Connection) -> None:
    """Creates a 'legacy-telegram' channel from TELEGRAM_BOT_TOKEN (if set)
    and backfills every existing users row onto it. Raises if there are
    existing users but no token to migrate them onto. Pulled out of
    `upgrade()` as a plain function (taking any SQLAlchemy Connection, not
    specifically an Alembic migration context) so it's unit-testable against
    an in-memory SQLite engine without invoking the Alembic CLI at all —
    see `tests/test_migration_0002_backfill.py`.
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
```

- [ ] **Step 4b: Unit-test the backfill guard against a real (in-memory) SQLite connection**

Create `backend/tests/test_migration_0002_backfill.py`:

```python
import base64
import glob
import importlib.util
import secrets

import pytest
import sqlalchemy as sa


def _load_backfill_function():
    # The migration file's name has an Alembic-generated revision-id
    # prefix that isn't predictable ahead of time — find it by content
    # instead of a hardcoded filename.
    [path] = [p for p in glob.glob("migrations/versions/*.py") if "channels" in p]
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._backfill_users_channel


@pytest.fixture()
def _fake_encryption_key(monkeypatch):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from app import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture()
def _bare_connection():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE channels (id INTEGER PRIMARY KEY, key TEXT, display_name TEXT, "
                "channel_type TEXT, encrypted_credentials TEXT, is_active BOOLEAN, created_at DATETIME)"
            )
        )
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, channel_id INTEGER)"))
        yield connection


def test_backfill_raises_when_users_exist_and_no_token(monkeypatch, _fake_encryption_key, _bare_connection):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (1, NULL)"))

    backfill = _load_backfill_function()
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        backfill(_bare_connection)


def test_backfill_noop_when_no_users_and_no_token(monkeypatch, _fake_encryption_key, _bare_connection):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    backfill = _load_backfill_function()
    backfill(_bare_connection)  # must not raise

    assert _bare_connection.execute(sa.text("SELECT COUNT(*) FROM channels")).scalar() == 0


def test_backfill_creates_legacy_channel_and_attaches_existing_users(
    monkeypatch, _fake_encryption_key, _bare_connection
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "legacy-token-value")
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (1, NULL)"))
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (2, NULL)"))

    backfill = _load_backfill_function()
    backfill(_bare_connection)

    channels = _bare_connection.execute(sa.text("SELECT key, channel_type FROM channels")).fetchall()
    assert channels == [("legacy-telegram", "telegram")]

    channel_ids = _bare_connection.execute(sa.text("SELECT DISTINCT channel_id FROM users")).fetchall()
    assert len(channel_ids) == 1
    assert channel_ids[0][0] is not None
```

Run: `cd backend && python3.11 -m pytest tests/test_migration_0002_backfill.py -v`
Expected: PASS (3 tests) — write this after Step 4's migration file exists (the glob needs
a real file to find), so run it right after creating that file, before moving on.

- [ ] **Step 5: Run the migration against the real database**

```bash
cd backend
python3.11 -m alembic upgrade head
```

Expected: succeeds (the real `.env` already has `TELEGRAM_BOT_TOKEN` set, and `local.db` has exactly 1 existing user from earlier manual testing this session).

- [ ] **Step 6: Verify the real database**

```bash
python3.11 - <<'EOF'
import sqlite3
conn = sqlite3.connect("local.db")
print("channels:", conn.execute("SELECT id, key, channel_type, is_active FROM channels").fetchall())
print("users:", conn.execute("SELECT id, channel_id, telegram_user_id FROM users").fetchall())
EOF
```

Expected: one `channels` row (`key="legacy-telegram"`), and the existing user row now has that channel's `id` as `channel_id`.

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/db/models.py backend/migrations/versions/0002_channels* backend/tests/conftest.py backend/tests/test_models.py backend/tests/test_admin_logs.py backend/tests/test_admin_users.py backend/tests/test_agent_graph.py backend/tests/test_agent_nodes.py backend/tests/test_migration_0002_backfill.py
git commit -m "feat(backend): add channels table, scope users by channel_id"
```

---

## Task 4: `ChannelManager`

**Files:**
- Create: `backend/app/channel_manager.py`
- Test: `backend/tests/test_channel_manager.py` (new)

**Interfaces:**
- Consumes: `Channel` model (Task 3), `app.crypto.decrypt` (Task 2), `app.telegram_poller.run_poller(channel_id, bot_token)` (Task 6 — patched out in this task's tests, since Task 6 hasn't reworked its signature yet; this task's tests patch `app.channel_manager.run_poller` directly so the exact real signature doesn't matter yet).
- Produces: `ChannelManager` class with `async def sync(self, db: Session) -> None` and `async def stop_all(self) -> None`; a module-level `channel_manager = ChannelManager()` singleton. Consumed by Task 6 (`telegram_poller.run_poller`'s real signature) and Task 7 (`admin_channels.py`, `main.py`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_channel_manager.py`:

```python
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.channel_manager import ChannelManager
from app.crypto import encrypt
from app.db.models import Channel


def _make_channel(db_session, key: str, bot_token: str, is_active: bool = True, channel_type: str = "telegram") -> Channel:
    channel = Channel(
        key=key,
        display_name=key,
        channel_type=channel_type,
        encrypted_credentials=encrypt(json.dumps({"bot_token": bot_token})),
        is_active=is_active,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


@pytest.mark.asyncio
async def test_sync_starts_a_task_for_a_new_active_channel(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)

        assert channel.id in manager._tasks
        mock_run_poller.assert_called_once_with(channel.id, "token-a")

        await manager.stop_all()


@pytest.mark.asyncio
async def test_sync_ignores_inactive_and_non_telegram_channels(db_session):
    _make_channel(db_session, "inactive", "token-x", is_active=False)
    _make_channel(db_session, "other-type", "token-y", channel_type="zalo")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        manager = ChannelManager()
        await manager.sync(db_session)

        assert manager._tasks == {}
        mock_run_poller.assert_not_called()


@pytest.mark.asyncio
async def test_sync_stops_task_for_deactivated_channel(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        task = manager._tasks[channel.id]

        channel.is_active = False
        db_session.commit()
        await manager.sync(db_session)

        assert channel.id not in manager._tasks
        assert task.cancelled() or task.cancelling()


@pytest.mark.asyncio
async def test_sync_restarts_task_when_token_changes(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        first_task = manager._tasks[channel.id]

        channel.encrypted_credentials = encrypt(json.dumps({"bot_token": "token-b"}))
        db_session.commit()
        await manager.sync(db_session)

        assert manager._tasks[channel.id] is not first_task
        mock_run_poller.assert_called_with(channel.id, "token-b")

        await manager.stop_all()


@pytest.mark.asyncio
async def test_sync_leaves_unchanged_channel_task_running(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        first_task = manager._tasks[channel.id]

        await manager.sync(db_session)

        assert manager._tasks[channel.id] is first_task
        assert mock_run_poller.call_count == 1

        await manager.stop_all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3.11 -m pytest tests/test_channel_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.channel_manager'`.

- [ ] **Step 3: Write `app/channel_manager.py`**

```python
import asyncio
import json
import logging

from sqlalchemy.orm import Session

from app.crypto import decrypt
from app.db.models import Channel
from app.telegram_poller import run_poller

logger = logging.getLogger(__name__)


class ChannelManager:
    """Keeps one long-poll `asyncio.Task` running per active Telegram
    channel, reconciled against the database on every `sync()` call — at
    app startup, and after every admin_channels.py mutation, so channel
    changes take effect without a process restart.
    """

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._tokens: dict[int, str] = {}

    async def sync(self, db: Session) -> None:
        active_channels = (
            db.query(Channel).filter_by(is_active=True, channel_type="telegram").all()
        )
        active_ids = {c.id for c in active_channels}

        for channel_id in list(self._tasks):
            if channel_id not in active_ids:
                await self._stop(channel_id)

        for channel in active_channels:
            try:
                bot_token = json.loads(decrypt(channel.encrypted_credentials))["bot_token"]
            except Exception:
                logger.exception("Failed to decrypt credentials for channel_id=%s; skipping", channel.id)
                continue

            if channel.id in self._tasks and self._tokens.get(channel.id) == bot_token:
                continue
            if channel.id in self._tasks:
                await self._stop(channel.id)

            self._tokens[channel.id] = bot_token
            self._tasks[channel.id] = asyncio.create_task(run_poller(channel.id, bot_token))

    async def _stop(self, channel_id: int) -> None:
        task = self._tasks.pop(channel_id, None)
        self._tokens.pop(channel_id, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def stop_all(self) -> None:
        for channel_id in list(self._tasks):
            await self._stop(channel_id)


channel_manager = ChannelManager()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_channel_manager.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/channel_manager.py backend/tests/test_channel_manager.py
git commit -m "feat(backend): add ChannelManager for dynamic per-channel Telegram pollers"
```

---

## Task 5: `telegram_client.py` takes `bot_token` per call

**Files:**
- Modify: `backend/app/telegram_client.py`
- Modify: `backend/tests/test_telegram_client.py`

**Interfaces:**
- Produces: `send_message(bot_token, chat_id, text) -> int | None`, `edit_message_text(bot_token, chat_id, message_id, text) -> None`, `get_updates(bot_token, offset, timeout=30) -> list[dict]`, `delete_webhook(bot_token) -> None`, `send_chat_action(bot_token, chat_id, action="typing") -> None`. Consumed by Task 6 (`telegram_poller.py`, `webhook.py`).

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/test_telegram_client.py` with:

```python
import httpx
import pytest

from app.telegram_client import send_chat_action, send_message


@pytest.mark.asyncio
async def test_send_message_posts_to_telegram_api():
    import respx

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )

        await send_message("TEST_TOKEN", chat_id="42", text="hello")

        assert route.called
        sent = route.calls.last.request
        assert b'"chat_id": "42"' in sent.content or b'"chat_id":"42"' in sent.content


@pytest.mark.asyncio
async def test_send_chat_action_posts_typing_to_telegram_api():
    import respx

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendChatAction").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await send_chat_action("TEST_TOKEN", chat_id="42")

        assert route.called
        sent = route.calls.last.request
        assert b'"action": "typing"' in sent.content or b'"action":"typing"' in sent.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3.11 -m pytest tests/test_telegram_client.py -v`
Expected: FAIL — `send_message()` (and `send_chat_action()`) still take `chat_id` as their first positional argument, so calling them with `bot_token` first raises a `TypeError` / the request goes to the wrong URL (no token interpolated), and the route in the test never gets hit as configured.

- [ ] **Step 3: Rewrite `app/telegram_client.py`**

```python
import logging

import httpx

logger = logging.getLogger(__name__)


async def send_message(bot_token: str, chat_id: str, text: str) -> int | None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        logger.error("Telegram sendMessage failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
    return response.json().get("result", {}).get("message_id")


async def edit_message_text(bot_token: str, chat_id: str, message_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url, json={"chat_id": chat_id, "message_id": message_id, "text": text}
        )
    if response.status_code >= 400:
        if "message is not modified" in response.text.lower():
            return
        logger.error("Telegram editMessageText failed: %s %s", response.status_code, response.text)
        response.raise_for_status()


async def get_updates(bot_token: str, offset: int | None, timeout: int = 30) -> list[dict]:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params: dict = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset
    async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
        response = await client.post(url, json=params)
    if response.status_code >= 400:
        logger.error("Telegram getUpdates failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
    return response.json().get("result", [])


async def delete_webhook(bot_token: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url)
    if response.status_code >= 400:
        logger.error("Telegram deleteWebhook failed: %s %s", response.status_code, response.text)
        response.raise_for_status()


async def send_chat_action(bot_token: str, chat_id: str, action: str = "typing") -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "action": action})
    if response.status_code >= 400:
        logger.error("Telegram sendChatAction failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_telegram_client.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/telegram_client.py backend/tests/test_telegram_client.py
git commit -m "refactor(backend): telegram_client functions take bot_token per call"
```

---

## Task 6: Poller + webhook rework, remove the HTTP webhook route

**Files:**
- Modify: `backend/app/telegram_poller.py`
- Modify: `backend/app/routers/webhook.py`
- Modify: `backend/app/main.py` (must be fixed in this same task — see Step 3)
- Modify: `backend/tests/conftest.py` (poller-disabling fixture must be replaced — see Step 3)
- Modify: `backend/tests/test_webhook.py` (large rewrite — the HTTP route is gone)

**Interfaces:**
- Consumes: `telegram_client.py`'s new per-call `bot_token` signatures (Task 5).
- Produces: `run_poller(channel_id: int, bot_token: str) -> None` (matches what Task 4's `ChannelManager` already calls), `process_telegram_message(channel_id: int, bot_token: str, chat_id: str, telegram_user_id: str, text: str, db: Session)`. Consumed by Task 7 (nothing new needed there beyond what Task 4 already wired).

- [ ] **Step 1: Rewrite `app/telegram_poller.py`**

```python
import asyncio
import logging

from app.db.base import SessionLocal
from app.routers.webhook import process_telegram_message
from app.telegram_client import delete_webhook, get_updates

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 30
_ERROR_BACKOFF = 5.0


async def run_poller(channel_id: int, bot_token: str) -> None:
    """Long-polls Telegram for new messages on behalf of one channel."""
    try:
        await delete_webhook(bot_token)
    except Exception:
        logger.exception("Failed to delete existing Telegram webhook for channel_id=%s", channel_id)

    offset: int | None = None
    logger.info("Telegram long-polling started for channel_id=%s", channel_id)
    while True:
        try:
            updates = await get_updates(bot_token, offset=offset, timeout=_POLL_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram getUpdates failed for channel_id=%s; retrying shortly", channel_id)
            await asyncio.sleep(_ERROR_BACKOFF)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                await _handle_update(channel_id, bot_token, update)
            except Exception:
                logger.exception(
                    "Failed to process Telegram update %s for channel_id=%s", update.get("update_id"), channel_id
                )


async def _handle_update(channel_id: int, bot_token: str, update: dict) -> None:
    message = update.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    db = SessionLocal()
    try:
        await process_telegram_message(channel_id, bot_token, chat_id, telegram_user_id, text, db)
    finally:
        db.close()
```

- [ ] **Step 2: Rewrite `app/routers/webhook.py`**

Replace the whole file with:

```python
import asyncio
import logging
import time
from typing import Callable

from sqlalchemy.orm import Session

from app.agent.clients import get_chroma_client, get_openai_client
from app.agent.graph import run_agent
from app.agent.nodes import extract_favourite
from app.agent.state import AgentState
from app.db.models import Message, User
from app.telegram_client import edit_message_text, send_chat_action, send_message

logger = logging.getLogger(__name__)

FALLBACK_REPLY = "Sorry, having trouble right now — please try again in a bit."
THINKING_PLACEHOLDER = "🤔 Đang suy nghĩ..."

_background_tasks: set[asyncio.Task] = set()
_TYPING_KEEPALIVE_INTERVAL = 4.0
_STREAM_EDIT_MIN_INTERVAL = 1.2


def _get_or_create_user(db: Session, channel_id: int, telegram_user_id: str) -> User:
    user = (
        db.query(User)
        .filter_by(channel_id=channel_id, telegram_user_id=telegram_user_id)
        .one_or_none()
    )
    if user is None:
        user = User(channel_id=channel_id, telegram_user_id=telegram_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class _StreamDeliverer:
    def __init__(self, loop: asyncio.AbstractEventLoop, bot_token: str, chat_id: str) -> None:
        self._loop = loop
        self._bot_token = bot_token
        self._chat_id = chat_id
        self.message_id: int | None = None
        self._last_sent = 0.0
        self._lock = asyncio.Lock()

    def on_delta(self, text: str) -> None:
        asyncio.run_coroutine_threadsafe(self._maybe_deliver(text), self._loop)

    async def finalize(self, text: str) -> None:
        async with self._lock:
            await self._send(text)

    async def _maybe_deliver(self, text: str) -> None:
        async with self._lock:
            now = time.monotonic()
            if self.message_id is not None and (now - self._last_sent) < _STREAM_EDIT_MIN_INTERVAL:
                return
            await self._send(text)

    async def _send(self, text: str) -> None:
        if not text:
            return
        try:
            if self.message_id is None:
                self.message_id = await send_message(self._bot_token, chat_id=self._chat_id, text=text)
            else:
                await edit_message_text(
                    self._bot_token, chat_id=self._chat_id, message_id=self.message_id, text=text
                )
            self._last_sent = time.monotonic()
        except Exception:
            logger.exception("stream delivery failed for chat_id=%s", self._chat_id)


async def _keepalive_typing(bot_token: str, chat_id: str, user_id: int) -> None:
    while True:
        await asyncio.sleep(_TYPING_KEEPALIVE_INTERVAL)
        try:
            await send_chat_action(bot_token, chat_id=chat_id, action="typing")
        except Exception:
            logger.exception("typing keepalive failed for user_id=%s", user_id)


async def process_telegram_message(
    channel_id: int, bot_token: str, chat_id: str, telegram_user_id: str, text: str, db: Session
):
    """Runs the agent for one incoming Telegram text message and delivers
    the reply. Called from the per-channel long-poll loop in
    `app.telegram_poller`."""
    if not chat_id or not telegram_user_id or not text:
        return {}

    user = _get_or_create_user(db, channel_id, telegram_user_id)

    if user.blocked:
        return {}

    db.add(Message(user_id=user.id, role="user", content=text))
    db.commit()

    state = AgentState(user_id=user.id, chat_id=chat_id, incoming_text=text)

    try:
        await send_chat_action(bot_token, chat_id=chat_id, action="typing")
    except Exception:
        logger.exception("send_chat_action failed for user_id=%s", user.id)

    loop = asyncio.get_running_loop()
    deliverer = _StreamDeliverer(loop, bot_token, chat_id)
    try:
        deliverer.message_id = await send_message(bot_token, chat_id=chat_id, text=THINKING_PLACEHOLDER)
    except Exception:
        logger.exception("thinking placeholder failed for user_id=%s", user.id)
    keepalive_task = asyncio.create_task(_keepalive_typing(bot_token, chat_id, user.id))

    try:
        result = await asyncio.to_thread(
            run_agent,
            state,
            db=db,
            chroma_client=get_chroma_client(),
            openai_client=get_openai_client(),
            on_delta=deliverer.on_delta,
        )
        reply = result.reply or FALLBACK_REPLY
    except Exception:
        logger.exception("Agent run failed for user_id=%s", user.id)
        reply = FALLBACK_REPLY
    finally:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    db.add(Message(user_id=user.id, role="assistant", content=reply))
    db.commit()

    try:
        if deliverer.message_id is not None:
            await deliverer.finalize(reply)
        else:
            await send_message(bot_token, chat_id=chat_id, text=reply)
    except Exception:
        logger.exception("send_message failed for user_id=%s", user.id)

    task = asyncio.create_task(_extract_favourite_background(state, user.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {}


async def _extract_favourite_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        await asyncio.to_thread(extract_favourite, state, db=db, openai_client=get_openai_client())
    except Exception:
        logger.exception("extract_favourite failed for user_id=%s", user_id)
    finally:
        db.close()
```

Note there is no `router = APIRouter()` and no `/webhook/telegram` route anymore — `app/main.py` (Task 7) stops importing `webhook.router`.

- [ ] **Step 3: Update `app/main.py` and `tests/conftest.py` in the same commit as this task**

Removing `webhook.router` and changing `run_poller`'s signature (above) breaks
`app/main.py` the instant this task lands — it still does
`from app.routers import ... webhook` and `asyncio.create_task(run_poller())` (no args).
That import/call must be fixed here, not deferred to Task 7, or the whole suite fails to
even collect (`app.main` fails to import). Task 7 will only need to add one router
registration on top of this.

Replace `app/main.py` with:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.channel_manager import channel_manager
from app.config import get_settings
from app.db.base import SessionLocal
from app.routers import admin_docs, admin_logs, admin_usage, admin_users, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_unsafe_defaults()
    db = SessionLocal()
    try:
        await channel_manager.sync(db)
    finally:
        db.close()
    try:
        yield
    finally:
        await channel_manager.stop_all()


def _warn_on_unsafe_defaults() -> None:
    settings = get_settings()
    if settings.admin_password == "admin" or settings.openai_api_key == "":
        logger.warning("Using default/empty admin or API credentials — do not deploy like this")


app = FastAPI(title="Matcha Bot Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
app.include_router(admin_users.login_router)
app.include_router(admin_logs.router)
app.include_router(admin_usage.router)
```

`app/main.py`'s lifespan now calls `channel_manager.sync(db)` with a `SessionLocal()`
bound to the **real** `DATABASE_URL` (not the test's in-memory `db_session` — the
`get_db` dependency override only affects request-time DB access, not this direct call).
Since Task 3's migration already inserted a real `legacy-telegram` channel with a real
bot token into `backend/local.db`, any test that instantiates `TestClient(app)` would
otherwise start a **real** long-poll task against the **real** Telegram API on every test
run. `tests/conftest.py`'s old `_disable_telegram_poller` fixture (which patched
`app.main.run_poller`, a name that no longer exists) must be replaced to prevent this.
Replace it with:

```python
@pytest.fixture(autouse=True)
def _disable_channel_manager(monkeypatch):
    from app.channel_manager import channel_manager

    async def _noop_sync(db):
        return None

    async def _noop_stop_all():
        return None

    monkeypatch.setattr(channel_manager, "sync", _noop_sync)
    monkeypatch.setattr(channel_manager, "stop_all", _noop_stop_all)
```

(Delete the old `_noop_poller` function and `_disable_telegram_poller` fixture along with
their now-stale `import asyncio` if nothing else in `conftest.py` needs it — check before
removing the import, since other fixtures may still use `asyncio`.)

- [ ] **Step 4: Rewrite `tests/test_webhook.py`**

The HTTP route is gone, so every test now calls `process_telegram_message` directly instead of `client.post("/webhook/telegram", ...)`. Replace the whole file with:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import User
from app.routers.webhook import THINKING_PLACEHOLDER, process_telegram_message


@pytest.mark.asyncio
async def test_process_message_creates_user_stores_message_and_replies(db_session, channel_id):
    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.edit_message_text", new_callable=AsyncMock
    ) as mock_edit, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ) as mock_typing, patch("app.routers.webhook.extract_favourite"), patch(
        "app.routers.webhook.get_chroma_client", return_value=MagicMock()
    ), patch("app.routers.webhook.get_openai_client", return_value=MagicMock()):
        mock_send.return_value = 555

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(channel_id, "TEST_TOKEN", "111", "111", "hi there", db_session)

    mock_send.assert_awaited_once()
    assert mock_send.call_args.args[0] == "TEST_TOKEN"
    assert mock_send.call_args.kwargs["text"] == THINKING_PLACEHOLDER
    mock_edit.assert_awaited_once_with("TEST_TOKEN", chat_id="111", message_id=555, text="Welcome!")
    mock_typing.assert_awaited_once_with("TEST_TOKEN", chat_id="111", action="typing")
    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="111").one()
    assert user is not None


@pytest.mark.asyncio
async def test_process_message_delivers_streamed_reply_progressively(db_session, channel_id):
    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.edit_message_text", new_callable=AsyncMock
    ) as mock_edit, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch("app.routers.webhook.extract_favourite"), patch(
        "app.routers.webhook.get_chroma_client", return_value=MagicMock()
    ), patch("app.routers.webhook.get_openai_client", return_value=MagicMock()):
        mock_send.return_value = 999

        def fake_run_agent(state, **kwargs):
            on_delta = kwargs["on_delta"]
            on_delta("Try ")
            on_delta("Try our matcha!")
            state.reply = "Try our matcha!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(channel_id, "TEST_TOKEN", "222", "222", "hi there", db_session)

    mock_send.assert_awaited_once()
    assert mock_send.call_args.kwargs["text"] == THINKING_PLACEHOLDER
    assert mock_edit.await_count == 2
    mock_edit.assert_any_await("TEST_TOKEN", chat_id="222", message_id=999, text="Try ")
    mock_edit.assert_awaited_with("TEST_TOKEN", chat_id="222", message_id=999, text="Try our matcha!")


@pytest.mark.asyncio
async def test_keepalive_typing_refreshes_on_each_interval_tick():
    from app.routers.webhook import _keepalive_typing

    with patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock) as mock_typing, patch(
        "app.routers.webhook._TYPING_KEEPALIVE_INTERVAL", 0.02
    ):
        task = asyncio.create_task(_keepalive_typing("TEST_TOKEN", chat_id="444", user_id=1))
        await asyncio.sleep(0.09)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert mock_typing.await_count >= 3
    mock_typing.assert_awaited_with("TEST_TOKEN", chat_id="444", action="typing")


@pytest.mark.asyncio
async def test_keepalive_typing_survives_a_send_chat_action_failure():
    from app.routers.webhook import _keepalive_typing

    with patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock, side_effect=RuntimeError("boom")
    ) as mock_typing, patch("app.routers.webhook._TYPING_KEEPALIVE_INTERVAL", 0.02):
        task = asyncio.create_task(_keepalive_typing("TEST_TOKEN", chat_id="444", user_id=1))
        await asyncio.sleep(0.07)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert mock_typing.await_count >= 2


@pytest.mark.asyncio
async def test_process_message_skips_blocked_user(db_session, channel_id):
    blocked = User(channel_id=channel_id, telegram_user_id="222", blocked=True)
    db_session.add(blocked)
    db_session.commit()

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send:
        await process_telegram_message(channel_id, "TEST_TOKEN", "222", "222", "hello", db_session)

    mock_run_agent.assert_not_called()
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_swallows_send_message_failures(db_session, channel_id):
    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch("app.routers.webhook.extract_favourite"):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent
        mock_send.side_effect = RuntimeError("Telegram API error")

        await process_telegram_message(channel_id, "TEST_TOKEN", "333", "333", "hi there", db_session)

    assert mock_send.await_count == 2
    mock_send.assert_awaited_with("TEST_TOKEN", chat_id="333", text="Welcome!")
    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="333").one()
    assert user is not None


@pytest.mark.asyncio
async def test_process_message_background_favourite_extraction_actually_runs(db_session, channel_id):
    from tests.conftest import TestSessionLocal

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": "sencha"}'))
    ]

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ), patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch(
        "app.routers.webhook.get_openai_client", return_value=fake_openai
    ), patch("app.db.base.SessionLocal", TestSessionLocal):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(channel_id, "TEST_TOKEN", "777", "777", "I really love sencha the most", db_session)

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    from app.db.models import Favourite

    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="777").one()
    favourites = db_session.query(Favourite).filter_by(user_id=user.id).all()
    assert len(favourites) == 1
    assert favourites[0].drink_name == "sencha"
```

Note: the webhook-secret tests (`test_webhook_rejects_missing_secret_header_when_configured`,
`test_webhook_rejects_wrong_secret_header_when_configured`, `test_webhook_accepts_correct_secret_header`,
`test_webhook_proceeds_when_no_secret_configured`) are deleted along with the route and
`_verify_telegram_secret` — there is no more secret-header concept once there's no HTTP
endpoint for Telegram to call.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python3.11 -m pytest -q`
Expected: all tests pass (this is the first point where the whole suite is runnable again
after Task 6's breaking changes to `app.main`, so run the full suite here, not just
`test_webhook.py`).

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/telegram_poller.py backend/app/routers/webhook.py backend/app/main.py backend/tests/conftest.py backend/tests/test_webhook.py
git commit -m "refactor(backend): scope Telegram message processing by channel, drop HTTP webhook route"
```

---

## Task 7: `/admin/channels` CRUD API and app wiring

**Files:**
- Create: `backend/app/routers/admin_channels.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py` (remove now-unused `telegram_bot_token`, `telegram_webhook_secret`)
- Test: `backend/tests/test_admin_channels.py` (new)

**Interfaces:**
- Consumes: `Channel` model (Task 3), `encrypt`/`decrypt` (Task 2), `channel_manager` (Task 4).
- Produces: `POST /admin/channels`, `GET /admin/channels`, `PATCH /admin/channels/{id}`, `DELETE /admin/channels/{id}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_channels.py`:

```python
import json
from unittest.mock import AsyncMock, patch

from app.crypto import decrypt
from app.db.models import Channel


def test_create_channel_requires_auth(client):
    response = client.post("/admin/channels", json={"key": "a", "display_name": "A", "channel_type": "telegram", "bot_token": "t"})
    assert response.status_code == 401


def test_create_channel_encrypts_the_token_and_never_returns_it(client, db_session):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.post(
            "/admin/channels",
            json={"key": "my-bot", "display_name": "My Bot", "channel_type": "telegram", "bot_token": "secret-token"},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "my-bot"
    assert "bot_token" not in body
    assert "encrypted_credentials" not in body

    channel = db_session.query(Channel).filter_by(key="my-bot").one()
    assert channel.encrypted_credentials != "secret-token"
    assert json.loads(decrypt(channel.encrypted_credentials))["bot_token"] == "secret-token"
    mock_sync.assert_awaited_once()


def test_create_channel_rejects_unsupported_channel_type(client, db_session):
    response = client.post(
        "/admin/channels",
        json={"key": "zalo-bot", "display_name": "Zalo", "channel_type": "zalo", "bot_token": "t"},
        auth=("admin", "admin"),
    )
    assert response.status_code == 400
    assert db_session.query(Channel).count() == 0


def test_list_channels_never_includes_credentials(client, db_session, channel_id):
    response = client.get("/admin/channels", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "encrypted_credentials" not in body[0]
    assert "bot_token" not in body[0]
    assert body[0]["id"] == channel_id


def test_update_channel_toggles_active_and_syncs(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.patch(f"/admin/channels/{channel_id}", json={"is_active": False}, auth=("admin", "admin"))

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    mock_sync.assert_awaited_once()


def test_update_channel_can_rotate_the_bot_token(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        client.patch(f"/admin/channels/{channel_id}", json={"bot_token": "new-token"}, auth=("admin", "admin"))

    channel = db_session.query(Channel).filter_by(id=channel_id).one()
    assert json.loads(decrypt(channel.encrypted_credentials))["bot_token"] == "new-token"


def test_delete_channel_removes_it_and_syncs(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Channel).count() == 0
    mock_sync.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3.11 -m pytest tests/test_admin_channels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.admin_channels'`.

- [ ] **Step 3: Write `app/routers/admin_channels.py`**

```python
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_admin
from app.channel_manager import channel_manager
from app.crypto import encrypt
from app.db.base import get_db
from app.db.models import Channel

router = APIRouter(prefix="/admin/channels")

ALLOWED_CHANNEL_TYPES = ("telegram",)


class ChannelCreate(BaseModel):
    key: str
    display_name: str
    channel_type: str
    bot_token: str


class ChannelUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    bot_token: str | None = None


def _serialize(channel: Channel) -> dict:
    return {
        "id": channel.id,
        "key": channel.key,
        "display_name": channel.display_name,
        "channel_type": channel.channel_type,
        "is_active": channel.is_active,
        "created_at": channel.created_at.isoformat(),
    }


def _get_channel_or_404(db: Session, channel_id: int) -> Channel:
    channel = db.query(Channel).filter_by(id=channel_id).one_or_none()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("", status_code=201)
async def create_channel(
    payload: ChannelCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    if payload.channel_type not in ALLOWED_CHANNEL_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported channel_type: {payload.channel_type}")

    channel = Channel(
        key=payload.key,
        display_name=payload.display_name,
        channel_type=payload.channel_type,
        encrypted_credentials=encrypt(json.dumps({"bot_token": payload.bot_token})),
        is_active=True,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    log_admin_action(db, action="create_channel", target=channel.key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)

    return _serialize(channel)


@router.get("")
def list_channels(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    return [_serialize(c) for c in channels]


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    channel = _get_channel_or_404(db, channel_id)

    if payload.display_name is not None:
        channel.display_name = payload.display_name
    if payload.is_active is not None:
        channel.is_active = payload.is_active
    if payload.bot_token is not None:
        channel.encrypted_credentials = encrypt(json.dumps({"bot_token": payload.bot_token}))

    db.commit()
    db.refresh(channel)

    log_admin_action(db, action="update_channel", target=channel.key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)

    return _serialize(channel)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    channel = _get_channel_or_404(db, channel_id)
    key = channel.key

    db.delete(channel)
    db.commit()

    log_admin_action(db, action="delete_channel", target=key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)
```

- [ ] **Step 4: Register the new router in `app/main.py`**

`app/main.py` was already rewritten in Task 6 (it had to be, to stop importing the
now-deleted `webhook.router` and the now-reworked `run_poller`). This step just adds the
new router on top of that. Change the import line from:

```python
from app.routers import admin_docs, admin_logs, admin_usage, admin_users, health
```

to:

```python
from app.routers import admin_channels, admin_docs, admin_logs, admin_usage, admin_users, health
```

And add, right after `app.include_router(health.router)`:

```python
app.include_router(admin_channels.router)
```

- [ ] **Step 5: Remove now-unused settings from `app/config.py`**

Remove the `telegram_bot_token` and `telegram_webhook_secret` fields — nothing reads them
anymore (the migration in Task 3 reads `TELEGRAM_BOT_TOKEN` directly from `os.environ`, not
via `Settings`). `Settings` should now read:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    chroma_persist_dir: str = "./chroma_db"
    encryption_key: str = ""
    database_url: str = "sqlite:///./local.db"
    admin_username: str = "admin"
    admin_password: str = "admin"
```

- [ ] **Step 6: Run the full suite**

Run: `cd backend && python3.11 -m pytest tests/test_admin_channels.py -v`
Expected: PASS (7 tests).

Run: `cd backend && python3.11 -m pytest -q`
Expected: all tests pass. `test_channel_manager.py`'s tests are unaffected by the
`_disable_channel_manager` autouse fixture (added back in Task 6) since they use
`db_session` directly and construct their own `ChannelManager()` instances rather than the
patched module-level `channel_manager` singleton.

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/routers/admin_channels.py backend/app/main.py backend/app/config.py backend/tests/test_admin_channels.py
git commit -m "feat(backend): add /admin/channels CRUD API, wire ChannelManager into app lifespan"
```

---

## Task 8: `admin_users.py` shows which channel a user belongs to

**Files:**
- Modify: `backend/app/routers/admin_users.py`
- Modify: `backend/tests/test_admin_users.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_admin_users.py`, update `test_list_users_returns_summary` to assert the new field:

```python
def test_list_users_returns_summary(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user.id, drink_name="matcha"))
    db_session.commit()

    response = client.get("/admin/users", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["telegram_user_id"] == "1"
    assert body[0]["channel_id"] == channel_id
    assert body[0]["message_count"] == 1
    assert body[0]["favourites"] == ["matcha"]
    assert body[0]["blocked"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3.11 -m pytest tests/test_admin_users.py::test_list_users_returns_summary -v`
Expected: FAIL — `KeyError: 'channel_id'`.

- [ ] **Step 3: Add `channel_id` to `list_users`' response**

In `backend/app/routers/admin_users.py`, change the `result.append({...})` block inside
`list_users` from:

```python
        result.append(
            {
                "id": u.id,
                "telegram_user_id": u.telegram_user_id,
                "first_seen": u.first_seen.isoformat(),
                "message_count": message_count,
                "favourites": favourites,
                "blocked": u.blocked,
            }
        )
```

to:

```python
        result.append(
            {
                "id": u.id,
                "channel_id": u.channel_id,
                "telegram_user_id": u.telegram_user_id,
                "first_seen": u.first_seen.isoformat(),
                "message_count": message_count,
                "favourites": favourites,
                "blocked": u.blocked,
            }
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_admin_users.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/routers/admin_users.py backend/tests/test_admin_users.py
git commit -m "feat(backend): include channel_id in admin user listing"
```

---

## Task 9: Frontend "Channels" tab

**Files:**
- Create: `frontend/src/channels/ChannelsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

**Interfaces:**
- Consumes: `apiFetch<T>()` from `frontend/src/api/client.ts` (existing), `/admin/channels` endpoints (Task 7).

- [ ] **Step 1: Create `frontend/src/channels/ChannelsPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface Channel {
  id: number;
  key: string;
  display_name: string;
  channel_type: string;
  is_active: boolean;
  created_at: string;
}

const CHANNEL_TYPES: { value: string; label: string; enabled: boolean }[] = [
  { value: "telegram", label: "Telegram", enabled: true },
  { value: "zalo", label: "Zalo (coming soon)", enabled: false },
];

const EMPTY_FORM = { key: "", display_name: "", channel_type: "telegram", bot_token: "" };

export function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  async function loadChannels(): Promise<void> {
    try {
      const data = await apiFetch<Channel[]>("/admin/channels");
      setChannels(data);
      setError(null);
    } catch {
      setError("Failed to load channels");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadChannels();
  }, []);

  async function toggleActive(channel: Channel): Promise<void> {
    try {
      await apiFetch(`/admin/channels/${channel.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !channel.is_active }),
      });
      await loadChannels();
    } catch {
      setError("Failed to update channel");
    }
  }

  async function deleteChannel(channel: Channel): Promise<void> {
    try {
      await apiFetch(`/admin/channels/${channel.id}`, { method: "DELETE" });
      await loadChannels();
    } catch {
      setError("Failed to delete channel");
    }
  }

  async function createChannel(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch("/admin/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setForm(EMPTY_FORM);
      setShowForm(false);
      await loadChannels();
    } catch {
      setError("Failed to create channel");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Channels</h1>
          <p className="text-sm text-muted-foreground">Chat platform connections (Telegram, and more soon).</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark"
        >
          + Add Channel
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {showForm && (
        <form onSubmit={createChannel} className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-card">
          <div>
            <label className="block text-sm font-medium text-foreground">Key</label>
            <input
              required
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              placeholder="my-telegram-bot"
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Display Name</label>
            <input
              required
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              placeholder="Sales Bot"
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Channel Type</label>
            <select
              value={form.channel_type}
              onChange={(e) => setForm({ ...form, channel_type: e.target.value })}
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            >
              {CHANNEL_TYPES.map((t) => (
                <option key={t.value} value={t.value} disabled={!t.enabled}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Bot Token</label>
            <input
              required
              type="password"
              value={form.bot_token}
              onChange={(e) => setForm({ ...form, bot_token: e.target.value })}
              placeholder="123456:ABC-DEF..."
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full">
          <thead>
            <tr>
              <th>Key</th>
              <th>Display Name</th>
              <th>Type</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  Loading channels…
                </td>
              </tr>
            ) : channels.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  No channels yet — add one to connect a bot.
                </td>
              </tr>
            ) : (
              channels.map((channel) => (
                <tr key={channel.id}>
                  <td className="font-medium text-foreground">{channel.key}</td>
                  <td>{channel.display_name}</td>
                  <td className="text-muted-foreground">{channel.channel_type}</td>
                  <td>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        channel.is_active ? "bg-primary-light text-primary-dark" : "bg-red-50 text-red-700"
                      }`}
                    >
                      {channel.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="flex gap-2">
                    <button
                      onClick={() => toggleActive(channel)}
                      className="rounded px-2 py-1 text-sm font-medium text-primary hover:bg-primary-light"
                    >
                      {channel.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => deleteChannel(channel)}
                      className="rounded px-2 py-1 text-sm font-medium text-red-700 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add the route in `frontend/src/App.tsx`**

Add the import:

```tsx
import { ChannelsPage } from "./channels/ChannelsPage";
```

Add the route inside the `/panel` route's children, after `usage`:

```tsx
            <Route path="usage" element={<UsagePage />} />
            <Route path="channels" element={<ChannelsPage />} />
```

- [ ] **Step 3: Add the nav link in `frontend/src/layout/AppShell.tsx`**

Add, after the `Usage` `NavLink`:

```tsx
        <NavLink to="/panel/channels" className={linkClass}>
          Channels
        </NavLink>
```

- [ ] **Step 4: Manually verify in the browser**

Run: `cd frontend && npm run dev` (or the project's existing dev-server command), log into the admin panel, navigate to the new "Channels" tab, confirm the existing `legacy-telegram` channel (created by Task 3's migration) is listed, and that creating/deactivating/deleting a test channel round-trips correctly against the real backend.

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add frontend/src/channels frontend/src/App.tsx frontend/src/layout/AppShell.tsx
git commit -m "feat(frontend): add Channels admin tab"
```

---

## Task 10: Final integration verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && python3.11 -m pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Confirm no leftover references to the removed globals**

```bash
grep -rn "telegram_bot_token\|telegram_webhook_secret\|get_qdrant_client\|/webhook/telegram" backend/app backend/tests
```

Expected: no output.

- [ ] **Step 3: Restart the backend for real and confirm the legacy channel's poller starts**

Restart the running `uvicorn app.main:app` process (kill the old one, start
`python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8000` fresh from `backend/`, per
this project's established local-dev pattern). Check its log output for
`"Telegram long-polling started for channel_id=<id>"` matching the `legacy-telegram`
channel created by Task 3's migration.

- [ ] **Step 4: Manual end-to-end smoke test**

Send a message to the live Telegram bot and confirm it still replies (proving the
migrated `legacy-telegram` channel's token round-tripped correctly through encryption and
the new `ChannelManager`-driven poller). Then, in the admin UI's new Channels tab, create a
second test channel pointing at a throwaway/invalid token, confirm it appears and its
poller starts (check the log for a second `"Telegram long-polling started for
channel_id=..."` line, and a `getUpdates failed` retry loop for the invalid token — proving
one bad channel doesn't affect the working one), then delete it and confirm its task stops.
