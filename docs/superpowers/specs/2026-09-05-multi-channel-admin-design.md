# Multi-channel admin (DB-driven channel connections)

## Problem

The bot's Telegram connection is a single hardcoded `TELEGRAM_BOT_TOKEN` in
`backend/.env`, read via `app/config.py`'s `Settings` and re-read from
`get_settings()` in every `app/telegram_client.py` function. Changing bots
means editing `.env` and restarting the process. There's no way to run more
than one bot, and no path to add another platform (Zalo, etc.) without
another hardcoded token + another bespoke poller.

This adds an admin-managed `channels` table: multiple channel connections
(today: multiple Telegram bot instances; other platform types are
selectable in the UI but inert placeholders), created/edited/deleted
through a new admin API and a new "Channels" tab in the frontend, with
credentials encrypted at rest and pollers started/stopped dynamically as
channels change — no process restart needed.

## Decisions locked in with the user

- **Multiple instances per channel type**: yes — e.g. two different
  Telegram bots can run concurrently, each scoped as its own "channel."
  This means `User`/`Message` must be scoped by `channel_id`, not just
  `telegram_user_id` (the same Telegram user id can exist independently
  under two different bots).
- **Only Telegram is functional**: other channel types (Zalo, etc.) appear
  in the UI's channel-type selector but are disabled ("coming soon") —
  no real integration work for them in this project.
- **Credentials encrypted at rest**: AES-GCM, via a new `ENCRYPTION_KEY`
  env var. Tokens are never returned decrypted by the admin API after
  creation — changing a bot's token means re-entering it, not editing
  existing plaintext.
- **Alembic gets wired up for real**: currently a listed dependency with
  an `alembic.ini` pointing at a `migrations/` directory that doesn't
  exist — schema has been managed ad hoc. Adding a NOT NULL `channel_id`
  to the existing `users` table (which already has real rows) needs a
  proper migration with backfill, not `Base.metadata.create_all()`. This
  is additional, unplanned-for scope the user explicitly approved.
- The old `/webhook/telegram` route and its `_verify_telegram_secret`
  logic are removed — this project already moved to Telegram long-polling
  earlier (see `app/telegram_poller.py`), so the webhook route is dead
  code, and it bakes in the single-global-token assumption this rework
  removes.

## Architecture

```
Admin creates/edits/deletes a channel
  -> POST/PATCH/DELETE /admin/channels/*  (app/routers/admin_channels.py)
     - encrypts credentials (app/crypto.py) before writing to `channels`
     - never returns decrypted credentials
     - calls channel_manager.sync(db) so the change takes effect immediately

ChannelManager (app/channel_manager.py, one process-wide instance)
  - holds {channel_id: asyncio.Task} for every active Telegram channel
  - sync(db): diffs DB state vs running tasks
      - stop tasks for channels that are gone/deactivated
      - start tasks for new active channels
      - restart a task if its decrypted bot_token changed
  - called once at app startup (main.py lifespan) and after every
    admin_channels.py mutation

app/telegram_poller.py::run_poller(channel_id, bot_token)
  - same long-poll loop as today, but parameterized per channel instead
    of reading a single global token
  - hands each update to process_telegram_message(channel_id, bot_token, ...)

app/routers/webhook.py::process_telegram_message(channel_id, bot_token, chat_id, telegram_user_id, text, db)
  - resolves/creates the User scoped to (channel_id, telegram_user_id)
  - passes bot_token through to _StreamDeliverer for send_message/edit_message_text
  - everything downstream (fetch_history, retrieve, generate) is unchanged:
    since User is now unique per (channel_id, telegram_user_id), a plain
    user_id foreign key on Message already isolates history correctly
    per channel with no changes needed in app/agent/*
```

## Data model

```
channels
  id                     PK
  key                    unique slug, e.g. "my-telegram-bot"
  display_name           e.g. "Sales Bot"
  channel_type           "telegram" (only functional value for now;
                          the API rejects any other value on create)
  encrypted_credentials  AES-GCM ciphertext (base64), decrypts to JSON
                          e.g. {"bot_token": "..."} for telegram
  is_active              bool, default true
  created_at

users  (existing table, modified)
  + channel_id           FK -> channels.id, NOT NULL after backfill
  unique constraint moves from (telegram_user_id) alone to
  (channel_id, telegram_user_id)
```

`messages`, `favourites`, `token_usage` are unaffected — they key off
`user_id`, which is already correctly isolated once `users` is
channel-scoped.

## Credential encryption

`app/crypto.py`: `encrypt(plaintext: str) -> str` / `decrypt(ciphertext: str) -> str`
using `cryptography`'s `AESGCM` with a random 12-byte nonce prepended to
the ciphertext, both base64-encoded together. The key comes from a new
`Settings.encryption_key` (base64-encoded 32 random bytes, generated once
via `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
and set as `ENCRYPTION_KEY` in `.env`). A channel's credentials are
encrypted on write and only ever decrypted server-side (by
`ChannelManager.sync()` to start a poller, and never sent back over the
admin API).

## Migration bootstrap

Two Alembic migrations:

1. **Baseline** — an autogenerated migration reflecting the current schema
   (`users`, `messages`, `favourites`, `documents`, `admin_audit_log`,
   `token_usage`) as it exists today, so Alembic has a starting point.
   Applied via `alembic stamp head` against the existing `local.db` (it
   already has this schema — no DDL actually needs to run against it),
   and via a normal `alembic upgrade head` for any fresh database.
2. **Add channels + scope users** —
   - `CREATE TABLE channels (...)`.
   - `ALTER TABLE users ADD COLUMN channel_id INTEGER` (nullable).
   - Data migration: read `TELEGRAM_BOT_TOKEN` directly from
     `os.environ` (not via `Settings`, so this works standalone at
     migration time). If set, insert one `channels` row (`key =
     "legacy-telegram"`, `display_name = "Telegram (migrated)"`,
     `channel_type = "telegram"`, credentials encrypted from that token,
     `is_active = true`), then `UPDATE users SET channel_id = <that
     id>`. If `TELEGRAM_BOT_TOKEN` is unset but `users` has existing
     rows, the migration raises a clear error telling the operator to
     set it before migrating (this only affects this project's own
     database, which does have 2 existing users from testing). If
     `users` is empty, no legacy channel is created.
   - `ALTER TABLE users` to make `channel_id` `NOT NULL` and replace the
     old unique constraint on `telegram_user_id` with a composite
     unique constraint on `(channel_id, telegram_user_id)` (SQLite
     requires a table rebuild for constraint changes — Alembic's
     `batch_alter_table` handles this).

After this migration, `Settings.telegram_bot_token` is removed from
`app/config.py` — the app no longer reads a bot token from `.env` at
runtime; only the migration script touches the raw environment variable,
once, for the legacy backfill.

## Components touched

| File | Change |
|---|---|
| `app/db/models.py` | Add `Channel` model. Add `channel_id` FK + composite unique constraint to `User`. |
| `app/crypto.py` (new) | `encrypt()`/`decrypt()` via AES-GCM. |
| `app/channel_manager.py` (new) | `ChannelManager` class + module-level `channel_manager` instance: `sync(db)`, `stop_all()`. |
| `app/telegram_client.py` | Every function (`send_message`, `edit_message_text`, `get_updates`, `delete_webhook`, `send_chat_action`) takes `bot_token` as its first parameter instead of calling `get_settings()`. |
| `app/telegram_poller.py` | `run_poller(channel_id, bot_token)` — parameterized, no longer reads global settings; `_handle_update` threads `channel_id`/`bot_token` through. |
| `app/routers/webhook.py` | `_get_or_create_user` takes `channel_id`. `process_telegram_message` takes `channel_id, bot_token, ...`. `_StreamDeliverer` takes `bot_token`. The `/webhook/telegram` route, `_verify_telegram_secret`, and `THINKING_PLACEHOLDER`'s HTTP-webhook-specific wiring are removed (the route itself is deleted; the shared message-processing logic moves to being called only from the poller). |
| `app/routers/admin_users.py` | `list_users` already keys everything off `user.id` (not `telegram_user_id`), so blocking/unblocking needs no change. Add `channel_id` (and its `key`) to the list response only, so an admin looking at users can tell which bot each one came from once more than one channel exists. |
| `app/routers/admin_channels.py` (new) | `/admin/channels` CRUD: `POST` (create, encrypts credentials), `GET` (list, never includes credentials), `PATCH /{id}` (toggle `is_active`, update `display_name`, optionally rotate `bot_token`), `DELETE /{id}`. Each mutation calls `channel_manager.sync(db)`. |
| `app/main.py` | Lifespan: replace the single global `run_poller()` task with `channel_manager.sync(db)` at startup and `channel_manager.stop_all()` at shutdown. |
| `app/config.py` | Remove `telegram_bot_token`, `telegram_webhook_secret` (webhook removed). Add `encryption_key: str = ""`. |
| `alembic.ini`, `migrations/` (new) | Wired up per the Migration bootstrap section. |
| `pyproject.toml` | Add `cryptography` dependency. |
| `frontend/src/channels/ChannelsPage.tsx` (new) | List + create/edit/delete UI, following `UsagePage.tsx`'s existing pattern (plain Tailwind, local `useState`/`useEffect`, `apiFetch`). Channel-type selector offers "Telegram" (enabled) and other types shown disabled with a "coming soon" label. |
| `frontend/src/layout/AppShell.tsx` | Add a `NavLink` to `/panel/channels`. |
| `frontend/src/App.tsx` | Add the `/panel/channels` route. |

## Error handling

- `ChannelManager.sync()` failing to decrypt one channel's credentials
  (e.g. `ENCRYPTION_KEY` rotated without re-entering tokens) logs and
  skips that channel rather than crashing the sync loop or other
  channels' pollers.
- A single channel's poller loop keeps its existing per-channel
  tolerance (retry/backoff on `getUpdates` failure, per-update exception
  isolation) — one broken bot token doesn't take down other channels.
- Admin API validates `channel_type` against the allowed set (`telegram`
  only) on create, returning `400` for anything else — this is what
  keeps Zalo/others as UI-only placeholders rather than accidentally
  creatable via direct API calls.

## Testing

- `app/crypto.py`: encrypt/decrypt round-trip; tampered ciphertext raises
  on decrypt.
- `app/channel_manager.py`: `sync()` starts a task for a new active
  channel, stops a task for a deactivated/deleted channel, restarts a
  task when the decrypted token changes, leaves an unchanged channel's
  task alone (asserted via task identity, not just call count) — all
  with `run_poller` patched out (no real network/long-poll in tests).
- `app/routers/admin_channels.py`: create encrypts the token (DB row's
  `encrypted_credentials` is never the plaintext token); list/get never
  include credentials; `channel_type` rejection for non-telegram values;
  update toggles `is_active` and triggers a `sync()` call; delete removes
  the row and triggers `sync()`; auth required on every route (mirroring
  `test_admin_docs.py`'s pattern).
- `app/telegram_client.py`: update the existing `test_telegram_client.py`
  tests to pass `bot_token` as an explicit argument instead of relying on
  `TELEGRAM_BOT_TOKEN`/`get_settings()`.
- `app/routers/webhook.py` / `app/telegram_poller.py`: update
  `test_webhook.py` (`process_telegram_message` signature gains
  `channel_id`/`bot_token`) — the webhook-route-specific tests
  (secret-header rejection, `/webhook/telegram` endpoint tests) are
  deleted along with the route.
- `app/routers/admin_users.py`: `list_users` includes `channel_id` in each
  row's response.
- Migration: a test that runs the two migrations against a fresh SQLite
  file with a pre-seeded legacy `users` row (simulating today's
  database) and asserts the row ends up with a valid `channel_id` and
  the new unique constraint is enforced.

## Out of scope

- Any real Zalo (or other platform) integration — UI-selectable but
  non-functional, as decided.
- Per-channel DM/Group policy, per-channel agent assignment, or any of
  goclaw's richer per-channel behavior configuration — this bot has one
  fixed agent pipeline; channels only vary by platform + credentials.
- A "reveal token" admin feature — tokens are write-only after creation.
- Migrating already-embedded Chroma knowledge base data — unrelated to
  this change.
