# 30-day inactive raw-message retention (GĐ3 of the matcha-bot enhancement roadmap)

## Problem

The `messages` table grows without bound — nothing ever deletes a
`Message` row. The original brief asks for the opposite: a customer
inactive for more than 30 days should have their raw conversation log
"forgotten", while the business-valuable memory the bot has already
distilled — the GĐ1 rolling summary and the GĐ2 customer profile —
stays intact.

This is gap **G3** from the case study
(`design /matcha-bot-case-study.html`), and it depends on both prior
phases: GĐ1's `conversation_summaries` and GĐ2's `customer_notes` are
what make deleting raw `Message` rows safe rather than destructive —
without them, purging a customer's messages would also erase every
allergy and preference the bot has learned about them.

## Decisions locked in with the user

- **Trigger mechanism**: an in-process `asyncio` loop started from
  `app/main.py`'s `lifespan`, following the exact shape already
  established by `run_poller()` in `app/telegram_poller.py` — a
  `while True` loop with `asyncio.sleep(interval)` between iterations,
  cancelled on shutdown the same way `channel_manager.stop_all()`
  cancels the Telegram poller tasks. No new job-scheduling dependency
  (no APScheduler, no Celery, no external cron) — matches the case
  study's stated principle of running periodic work in the existing
  backend process before reaching for heavier infrastructure.
- **Scan interval**: 24 hours. The 30-day threshold is coarse; there's
  no benefit to checking more often, and a daily scan keeps the added
  DB load negligible.
- **What's deleted vs. kept**: only raw `Message` rows for inactive
  users are deleted. `User`, `ConversationSummary`, and `CustomerNote`
  rows are never touched by this job — if an inactive customer
  returns, their profile and summary are still there, only the
  message-by-message transcript is gone.

## Architecture

```
Every incoming Telegram message (existing flow, extended):
  _get_or_create_user(db, channel_id, telegram_user_id)
    -> NEW: sets user.last_active_at = now() on every call (both the
       newly-created and the already-existing branch), committed
       alongside the existing user creation/lookup commit.

New module app/retention.py:
  purge_inactive_messages(db, inactive_days=30) -> int
    -> finds users where last_active_at < now - inactive_days
    -> deletes all Message rows for those users
    -> returns the number of rows deleted (for logging)
    -> does NOT touch User, ConversationSummary, or CustomerNote rows

  run_retention_loop(interval_seconds=86400) -> None
    while True:
      try: purge_inactive_messages(db, inactive_days=30)
      except CancelledError: raise
      except Exception: log and continue (retry next interval)
      await asyncio.sleep(interval_seconds)

app/main.py lifespan (extended, same pattern as channel_manager.sync()):
  startup: task = asyncio.create_task(run_retention_loop())
  shutdown: task.cancel(); await task
```

`purge_inactive_messages` is deliberately a plain, synchronous,
DB-only function with no `asyncio` in it — the same separation
`telegram_poller.py` doesn't have to make (it's I/O-bound throughout)
but this job benefits from: the actual deletion logic is fully
unit-testable without touching the event loop or real time, and
`run_retention_loop` is a thin wrapper whose only job is to call it on
a schedule.

## Components touched

| File | Change |
|---|---|
| `app/db/models.py` | `User` gains `last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`. |
| `migrations/versions/` | New Alembic migration adding the nullable `last_active_at` column to `users`. |
| `app/routers/webhook.py` | `_get_or_create_user()` sets `user.last_active_at = datetime.now(UTC)` and commits, for both the found and newly-created cases. |
| `app/retention.py` (new) | `purge_inactive_messages(db, inactive_days=30) -> int` and `run_retention_loop(interval_seconds=86400) -> None`, following `app/telegram_poller.py`'s `run_poller()` shape for the loop (try/except `asyncio.CancelledError` re-raised, other exceptions logged and swallowed so the loop keeps running). |
| `app/main.py` | `lifespan` starts `run_retention_loop()` as a background task alongside `channel_manager.sync()`, and cancels + awaits it on shutdown alongside `channel_manager.stop_all()`. |

## Error handling

- A DB error inside `purge_inactive_messages` during one scan is
  logged and the loop continues to the next interval — a transient
  failure doesn't stop future purges, and no partial state is left
  behind since the delete for each run is a single query executed
  inside one commit.
- `last_active_at` being `None` (a user row created before this
  migration, or — in practice never, since it's set at every
  `_get_or_create_user` call — but defensively) is treated as *not*
  eligible for purge: the query only matches
  `last_active_at IS NOT NULL AND last_active_at < cutoff`, so a
  missing timestamp never causes an unintended deletion.
- Deleting a user's messages while a chat turn for that same user is
  concurrently in flight is an accepted, extremely unlikely race (the
  user would have to send a message after 30 days of silence in the
  same instant the daily scan runs) — not handled specially, consistent
  with this codebase's existing tolerance for narrow races (see GĐ1's
  spec on the same topic for `maybe_summarize`).

## Testing

- `purge_inactive_messages()`:
  - a user active within the last 30 days keeps all their `Message`
    rows untouched.
  - a user whose `last_active_at` is more than 30 days in the past has
    all their `Message` rows deleted.
  - that same purged user's `ConversationSummary` and `CustomerNote`
    rows (if present) are untouched.
  - a user with `last_active_at` exactly at the 30-day boundary is not
    purged (boundary is strictly `<`, not `<=`).
  - a user with `last_active_at IS NULL` is not purged.
  - the returned count matches the number of `Message` rows actually
    deleted.
- `_get_or_create_user()` sets `last_active_at` to (approximately) now
  on both the newly-created-user path and the existing-user path.
- `run_retention_loop()`: with `asyncio.sleep` mocked (same pattern as
  the existing `patch("app.retry.time.sleep")` used elsewhere in this
  suite), assert one iteration calls `purge_inactive_messages` and
  that an exception raised by `purge_inactive_messages` doesn't
  propagate out of the loop (the loop calls it again on the next
  simulated iteration rather than dying).

## Out of scope

- Any UI surfacing retention activity (e.g. an admin log of what was
  purged and when) — not requested; `logger.info` on each run is
  sufficient for now, matching the log-only visibility the codebase
  already gives `telegram_poller`'s error backoff.
- Configurable retention window (e.g. an admin-settable "30 days") —
  the case study fixes this at 30 days; making it configurable is a
  separate, unrequested feature.
- Retroactively backfilling `last_active_at` for existing users via
  the migration (e.g. from their most recent `Message.created_at`) —
  the migration adds the column as nullable with no backfill; existing
  users simply get `last_active_at` set the next time they message the
  bot, and until then they're correctly treated as not-yet-eligible
  for purge (see "Error handling" above).
