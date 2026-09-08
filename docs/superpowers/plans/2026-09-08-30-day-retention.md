# 30-Day Inactive Raw-Message Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically delete raw `Message` rows for users inactive more than 30 days, while preserving their `ConversationSummary` (GĐ1) and `CustomerNote` (GĐ2) rows, so the bot "forgets" the transcript but not what it has learned about the customer.

**Architecture:** `User` gains a `last_active_at` column, touched on every incoming Telegram message. A new `app/retention.py` exposes a plain, synchronous `purge_inactive_messages(db, inactive_days=30) -> int` (fully unit-testable) and an `asyncio` wrapper `run_retention_loop(interval_seconds=86400)` that calls it on a schedule, following the exact `while True` / `asyncio.sleep` / `CancelledError`-reraise shape already used by `run_poller()` in `app/telegram_poller.py`. `app/main.py`'s `lifespan` starts and cancels this loop the same way it already manages `channel_manager`.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest (existing `db_session`/`channel_id` fixtures in `tests/conftest.py`, `pytest.mark.asyncio` for the loop test).

**Spec:** `docs/superpowers/specs/2026-09-08-30-day-retention-design.md`

## Global Constraints

- Only raw `Message` rows are deleted — `User`, `ConversationSummary`, and `CustomerNote` rows are never touched by this job.
- Retention threshold is fixed at 30 days, boundary is strictly `<` (a user exactly at 30 days is not yet purged).
- `last_active_at IS NULL` is never eligible for purge (treated as "not yet known", not "eligible").
- Trigger is an in-process `asyncio` loop (no APScheduler, no Celery, no external cron) — scan interval is 24 hours (86400 seconds).
- A purge failure must never crash the loop — it logs and retries on the next scheduled interval.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/db/models.py` | Add `User.last_active_at`. |
| `migrations/versions/0007_user_last_active_at.py` | New Alembic migration adding the nullable column. |
| `app/routers/webhook.py` | `_get_or_create_user()` sets `last_active_at` on every call. |
| `app/retention.py` (new) | `purge_inactive_messages()` and `run_retention_loop()`. |
| `app/main.py` | Starts/cancels the retention loop task in `lifespan`. |
| `tests/test_models.py` | (unchanged — `last_active_at` is exercised via the webhook and retention tests below, not a standalone model test; it's a plain nullable column with no constraint of its own to test in isolation). |
| `tests/test_webhook.py` | Test that `_get_or_create_user` sets `last_active_at`. |
| `tests/test_retention.py` (new) | Tests for `purge_inactive_messages()` and `run_retention_loop()`. |

---

### Task 1: `User.last_active_at` column + migration

**Files:**
- Modify: `app/db/models.py`
- Create: `migrations/versions/0007_user_last_active_at.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `User.last_active_at: datetime | None` (nullable, no default — set explicitly by callers). Task 2 (`webhook.py`) sets it; Task 3 (`retention.py`) reads it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` (it already imports `User` from `app.db.models`):

```python
def test_user_last_active_at_defaults_to_none(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="la1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.last_active_at is None


def test_user_last_active_at_can_be_set(db_session, channel_id):
    from datetime import UTC, datetime

    user = User(channel_id=channel_id, telegram_user_id="la2")
    db_session.add(user)
    db_session.commit()

    now = datetime.now(UTC)
    user.last_active_at = now
    db_session.commit()
    db_session.refresh(user)

    assert user.last_active_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py -k last_active_at -v`
Expected: FAIL with `AttributeError: 'User' object has no attribute 'last_active_at'` (or a `TypeError` from the unexpected keyword, depending on how the test touches the field — either way, a clear failure since the column doesn't exist yet)

- [ ] **Step 3: Add the column**

In `app/db/models.py`, add to the `User` class (after `blocked`):

```python
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models.py -k last_active_at -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Create `migrations/versions/0007_user_last_active_at.py`:

```python
"""add users.last_active_at

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_active_at")
```

- [ ] **Step 6: Verify the migration applies cleanly**

Run: `cd backend && rm -f local.db && alembic upgrade head && alembic current && rm -f local.db`
Expected: no errors, `alembic current` reports `0007 (head)`

- [ ] **Step 7: Commit**

```bash
git add app/db/models.py migrations/versions/0007_user_last_active_at.py tests/test_models.py
git commit -m "feat: add users.last_active_at column"
```

---

### Task 2: Set `last_active_at` on every incoming message

**Files:**
- Modify: `app/routers/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `User.last_active_at` (Task 1).
- Produces: `_get_or_create_user()` sets `last_active_at` to the current time on every call, for both the newly-created and already-existing user. Task 3 (`purge_inactive_messages`) relies on this being kept up to date to know who's still active.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_webhook.py` (it already imports `User` from `app.db.models`; this test calls the private `_get_or_create_user` directly, so add it to the import):

```python
from app.routers.webhook import THINKING_PLACEHOLDER, _get_or_create_user, process_telegram_message
```

```python
def test_get_or_create_user_sets_last_active_at_for_a_new_user(db_session, channel_id):
    from datetime import UTC, datetime

    before = datetime.now(UTC)
    user = _get_or_create_user(db_session, channel_id, "la-new")
    after = datetime.now(UTC)

    assert user.last_active_at is not None
    assert before <= user.last_active_at <= after


def test_get_or_create_user_updates_last_active_at_for_an_existing_user(db_session, channel_id):
    from datetime import UTC, datetime, timedelta

    user = _get_or_create_user(db_session, channel_id, "la-existing")
    old_timestamp = datetime.now(UTC) - timedelta(days=5)
    user.last_active_at = old_timestamp
    db_session.commit()

    user_again = _get_or_create_user(db_session, channel_id, "la-existing")

    assert user_again.id == user.id
    assert user_again.last_active_at > old_timestamp
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_webhook.py -k last_active_at -v`
Expected: FAIL (`last_active_at` stays `None` / unchanged — nothing sets it yet)

- [ ] **Step 3: Implement**

In `app/routers/webhook.py`, add the import (`datetime`/`UTC` aren't imported yet — add alongside the existing `asyncio`/`logging`/`time` imports):

```python
from datetime import UTC, datetime
```

Update `_get_or_create_user`:

```python
def _get_or_create_user(db: Session, channel_id: int, telegram_user_id: str) -> User:
    user = db.query(User).filter_by(channel_id=channel_id, telegram_user_id=telegram_user_id).one_or_none()
    if user is None:
        user = User(channel_id=channel_id, telegram_user_id=telegram_user_id)
        db.add(user)
    user.last_active_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_webhook.py -k last_active_at -v`
Expected: PASS

- [ ] **Step 5: Run the full webhook test file to check for regressions**

Run: `cd backend && pytest tests/test_webhook.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routers/webhook.py tests/test_webhook.py
git commit -m "feat: track last_active_at on every incoming message"
```

---

### Task 3: `purge_inactive_messages()`

**Files:**
- Create: `app/retention.py`
- Test: `tests/test_retention.py` (new)

**Interfaces:**
- Consumes: `User.last_active_at` (Task 1), `Message`, `ConversationSummary`, `CustomerNote` (all from `app.db.models`).
- Produces: `purge_inactive_messages(db: Session, inactive_days: int = 30) -> int`. Task 4 (`run_retention_loop`) calls this on a schedule.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_retention.py`:

```python
from datetime import UTC, datetime, timedelta

from app.db.models import ConversationSummary, CustomerNote, Message, User
from app.retention import purge_inactive_messages


def _user_with_last_active(db_session, channel_id, telegram_user_id, days_ago):
    user = User(
        channel_id=channel_id,
        telegram_user_id=telegram_user_id,
        last_active_at=datetime.now(UTC) - timedelta(days=days_ago) if days_ago is not None else None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_purge_keeps_messages_for_a_recently_active_user(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p1", days_ago=5)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1


def test_purge_deletes_messages_for_a_user_inactive_over_30_days(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p2", days_ago=31)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Message(user_id=user.id, role="assistant", content="hello"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 2
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 0


def test_purge_keeps_summary_and_notes_for_a_purged_user(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p3", days_ago=45)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(ConversationSummary(user_id=user.id, summary_text="likes hojicha"))
    db_session.add(CustomerNote(user_id=user.id, note_type="allergy", value="dairy"))
    db_session.commit()

    purge_inactive_messages(db_session, inactive_days=30)

    assert db_session.query(Message).filter_by(user_id=user.id).count() == 0
    assert db_session.query(ConversationSummary).filter_by(user_id=user.id).count() == 1
    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 1
    assert db_session.query(User).filter_by(id=user.id).count() == 1


def test_purge_does_not_delete_at_exactly_the_boundary(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p4", days_ago=30)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1


def test_purge_ignores_users_with_no_last_active_at(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p5", days_ago=None)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_retention.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.retention'`

- [ ] **Step 3: Implement**

Create `app/retention.py`:

```python
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, User

logger = logging.getLogger(__name__)

_SCAN_INTERVAL_SECONDS = 86400


def purge_inactive_messages(db: Session, inactive_days: int = 30) -> int:
    """Deletes raw `Message` rows for users whose `last_active_at` is more
    than `inactive_days` in the past. Never touches `User`,
    `ConversationSummary`, or `CustomerNote` rows — only the raw transcript
    is considered disposable. A user with `last_active_at IS NULL` (not yet
    set) is never eligible. Returns the number of `Message` rows deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
    inactive_user_ids = (
        db.execute(
            select(User.id).where(User.last_active_at.is_not(None), User.last_active_at < cutoff)
        )
        .scalars()
        .all()
    )
    if not inactive_user_ids:
        return 0

    messages = (
        db.execute(select(Message).where(Message.user_id.in_(inactive_user_ids))).scalars().all()
    )
    count = len(messages)
    for message in messages:
        db.delete(message)
    db.commit()
    return count
```

(`_SCAN_INTERVAL_SECONDS` is defined here now so Task 4 can import it as
the default for `run_retention_loop`'s `interval_seconds` parameter.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_retention.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/retention.py tests/test_retention.py
git commit -m "feat: add purge_inactive_messages"
```

---

### Task 4: `run_retention_loop()`

**Files:**
- Modify: `app/retention.py`
- Test: `tests/test_retention.py`

**Interfaces:**
- Consumes: `purge_inactive_messages` (Task 3), `SessionLocal` (`app.db.base`).
- Produces: `run_retention_loop(interval_seconds: int = _SCAN_INTERVAL_SECONDS) -> None`. Task 5 (`main.py`) starts this as a background task.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_retention.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.retention import run_retention_loop


@pytest.mark.asyncio
async def test_run_retention_loop_calls_purge_each_iteration(db_session):
    from tests.conftest import TestSessionLocal

    call_count = 0

    def fake_purge(db, inactive_days=30):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError()
        return 0

    with (
        patch("app.retention.SessionLocal", TestSessionLocal),
        patch("app.retention.purge_inactive_messages", side_effect=fake_purge),
        patch("app.retention.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_retention_loop(interval_seconds=0)

    assert call_count == 2


@pytest.mark.asyncio
async def test_run_retention_loop_survives_a_purge_failure(db_session):
    from tests.conftest import TestSessionLocal

    call_count = 0

    def fake_purge(db, inactive_days=30):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("db hiccup")
        raise asyncio.CancelledError()

    with (
        patch("app.retention.SessionLocal", TestSessionLocal),
        patch("app.retention.purge_inactive_messages", side_effect=fake_purge),
        patch("app.retention.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_retention_loop(interval_seconds=0)

    assert call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_retention.py -k run_retention_loop -v`
Expected: FAIL with `ImportError: cannot import name 'run_retention_loop'`

- [ ] **Step 3: Implement**

In `app/retention.py`, add the `asyncio` import and the loop function:

```python
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import Message, User

logger = logging.getLogger(__name__)

_SCAN_INTERVAL_SECONDS = 86400


def purge_inactive_messages(db: Session, inactive_days: int = 30) -> int:
    """Deletes raw `Message` rows for users whose `last_active_at` is more
    than `inactive_days` in the past. Never touches `User`,
    `ConversationSummary`, or `CustomerNote` rows — only the raw transcript
    is considered disposable. A user with `last_active_at IS NULL` (not yet
    set) is never eligible. Returns the number of `Message` rows deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
    inactive_user_ids = (
        db.execute(
            select(User.id).where(User.last_active_at.is_not(None), User.last_active_at < cutoff)
        )
        .scalars()
        .all()
    )
    if not inactive_user_ids:
        return 0

    messages = (
        db.execute(select(Message).where(Message.user_id.in_(inactive_user_ids))).scalars().all()
    )
    count = len(messages)
    for message in messages:
        db.delete(message)
    db.commit()
    return count


async def run_retention_loop(interval_seconds: int = _SCAN_INTERVAL_SECONDS) -> None:
    """Runs `purge_inactive_messages` on a fixed schedule for the lifetime
    of the process, following the same shape as `run_poller()` in
    `app/telegram_poller.py`: cancellation propagates immediately, any
    other failure is logged and the loop continues on the next
    interval."""
    logger.info("30-day message retention loop started")
    while True:
        db = SessionLocal()
        try:
            deleted = purge_inactive_messages(db)
            if deleted:
                logger.info("Retention purge deleted %s message(s)", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Retention purge failed; retrying next interval")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)
```

Note the full rewritten file replaces the `Task 3` version's imports (adds
`asyncio` and `from app.db.base import SessionLocal`) — the plan shows the
complete top-of-file state here so there's no ambiguity about what the
final import block looks like.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_retention.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/retention.py tests/test_retention.py
git commit -m "feat: add run_retention_loop scheduling wrapper"
```

---

### Task 5: Wire into app startup/shutdown

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `run_retention_loop` (Task 4, imported from `app.retention`).
- Produces: nothing further downstream — this is the last task, it makes the feature live end-to-end.

- [ ] **Step 1: Implement**

In `app/main.py`, add the import:

```python
from app.retention import run_retention_loop
```

Update `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_unsafe_defaults()
    db = SessionLocal()
    try:
        await channel_manager.sync(db)
    finally:
        db.close()
    retention_task = asyncio.create_task(run_retention_loop())
    try:
        yield
    finally:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
        await channel_manager.stop_all()
```

This requires `import asyncio` at the top of `app/main.py` — check
whether it's already imported; if not, add it alongside the existing
`import logging`.

- [ ] **Step 2: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: PASS, no regressions. (The app's existing `TestClient(app)`
fixture in `tests/conftest.py` exercises `lifespan` on every test that
uses the `client` fixture — if the retention task fails to start or
cancel cleanly, those tests will surface it. `run_retention_loop` isn't
directly mocked in this codebase's `client` fixture the way
`channel_manager.sync`/`stop_all` are, so this step is the check that
starting and then immediately cancelling a real `run_retention_loop`
task — with a real `SessionLocal()` doing one real, cheap
`purge_inactive_messages` query against the test's in-memory DB — works
without hanging or raising during test teardown.)

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: start the 30-day retention loop at app startup"
```

---

## Final Verification

- [ ] Run the full suite once more: `cd backend && pytest -v`
- [ ] Run `rm -f local.db && alembic upgrade head && alembic current` to confirm migration `0007` applies on top of `0006` cleanly, then `rm -f local.db`
- [ ] Manual sanity check (optional): temporarily set a test user's `last_active_at` far in the past directly in the DB, run the app, and confirm their `Message` rows disappear on the next scan while their `ConversationSummary`/`CustomerNote` rows remain
