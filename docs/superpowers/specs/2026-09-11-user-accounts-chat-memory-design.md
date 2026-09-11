# User Accounts + Chat Memory — Design

## Context

Customers no longer talk to the bot through Telegram. They register an account on the
login page and chat in the admin panel's **Chat** tab. The bot must remember each person's
preferences across conversations.

Today:

- Login is a single admin account from `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`),
  checked with HTTP Basic by `require_admin` (`backend/app/auth.py`). There is no account
  table.
- All memory — `Message`, `Favourite`, `ConversationSummary`, `CustomerNote`,
  `RecommendationHistory` — is keyed by `users.id`, and a `User` requires a `channel_id` and
  a `telegram_user_id`. Only Telegram customers get memory.
- `POST /admin/chat` (`backend/app/routers/admin_chat.py`) is stateless: the client sends
  the history, nothing is stored, and per-customer memory is skipped.

This spec is **step 1 of 5** of the memory roadmap (see §7). It adds accounts and makes the
Chat tab use the memory that already exists.

Decisions made during brainstorming:

1. **Every registered account gets full admin-panel access**, the same as the `.env` admin.
   There are no roles. (Chosen knowingly: any registered user can see logs, documents and
   settings.)
2. **Accounts map to memory through a shared "web" channel** (approach A): each account
   chats as a `User` on that channel. The memory tables and agent pipeline are unchanged.
3. **"Reset conversation" clears chat history only** — messages and the conversation
   summary. Favourites, customer notes and recommendation history are kept.
4. Registration takes **username + password only** — no email, no verification.
5. Telegram code stays as it is; it is simply no longer used.

## Precondition

The working tree holds uncommitted recommendation-history work (`app/agent/nodes.py`,
`app/agent/state.py`, `app/db/models.py`, `app/routers/webhook.py`, migrations `0009` and
`0010`, and their tests). This spec edits the same files and adds migration `0011` on top of
`0010`, so **that work must be committed before implementation starts**.

## 1. Accounts and authentication

### `accounts` table

New model `Account` in `app/db/models.py`, migration `0011_accounts.py`
(`down_revision = "0010"`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `username` | String, unique, indexed | |
| `password_hash` | String | `scrypt$<salt hex>$<hash hex>` |
| `created_at` | DateTime(tz) | default now |

There is no `user_id` column: the chat `User` is found by username (§2), which also lets
the `.env` admin chat with memory without an account row.

### Password hashing (`app/auth.py`)

- `hash_password(password: str) -> str`: 16 random bytes from `secrets.token_bytes`,
  `hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)`, stored as
  `scrypt$<salt.hex()>$<hash.hex()>`.
- `verify_password(password: str, stored: str) -> bool`: parses the stored value, recomputes
  with the same parameters, compares with `secrets.compare_digest`. A malformed stored value
  returns `False`.

No new dependency.

### `require_admin`

Keeps its name (every router depends on it); it now means "any signed-in account":

1. If the credentials match `ADMIN_USERNAME` / `ADMIN_PASSWORD`, allow — unchanged.
2. Otherwise look up `Account` by username; allow if `verify_password` passes.
3. Otherwise log `login_failed` and return 401 — unchanged.

It still returns the username. Basic auth re-checks on every request; one scrypt check is
roughly 50 ms and a page makes 1–3 requests, so there is no cache.

### `POST /auth/register`

New router `app/routers/auth_register.py`, registered in `app/main.py`. No authentication.

Request `{ "username": str, "password": str }`:

- `username`: 3–32 characters matching `^[A-Za-z0-9_.-]+$` → otherwise 422.
- `password`: at least 8 characters → otherwise 422.
- Username already in `accounts`, or equal to `ADMIN_USERNAME` → **409**
  `{"detail": "Username already taken"}`.

On success: insert the account, log audit action `account.register` with the username as
target, return **201** `{"username": ...}`. The endpoint does not sign the user in; the
frontend calls `login` afterwards.

## 2. The web channel and chat user

`get_web_user(db, username) -> User` in `app/routers/admin_chat.py`:

1. Find `Channel` with `key="web"`; if missing, create
   `Channel(key="web", display_name="Web chat", channel_type="web",
   encrypted_credentials="", is_active=True)`.
2. Find `User` with that `channel_id` and `telegram_user_id=username`; create it if missing.
3. Set `last_active_at` to now, commit, return the user.

Consequences:

- `channel_manager.sync` only starts channels with `channel_type="telegram"`, so the web
  channel starts no poller.
- `GET /admin/channels` filters out `channel_type == "web"`, so it cannot be edited or
  deleted from the Channels page.
- Web users appear on the Users and Access Log pages with their username in the ID column,
  and Block works for them.
- The 30-day retention purge applies to web users like any other.

## 3. Chat with memory

All three endpoints resolve the user from the Basic-auth username via `get_web_user`. None
accepts a user id from the client, so a person only ever reads or changes their own chat.

### `POST /admin/chat`

Request `{ "message": str }` — `message` stripped length ≥ 1 and length ≤ 4000, else 422.
The `history` field and `HISTORY_LIMIT` are removed.

Flow:

1. `user = get_web_user(db, username)`. If `user.blocked` → **403**
   `{"detail": "Your account is blocked"}`.
2. Daily limit: if `llm_settings.resolve(db).daily_token_limit` is set and
   `get_daily_token_total(db, user.id)` has reached it, save `Message(role="user")` and
   `Message(role="assistant", content=DAILY_LIMIT_REPLY)`, return
   `{"reply": DAILY_LIMIT_REPLY, "model": chat_model}` without calling the LLM.
3. Build `AgentState(user_id=user.id, chat_id=f"web:{user.id}", incoming_text=message)` and
   run `run_agent` (the full graph, including `fetch_history`) in `asyncio.to_thread`. The
   current message is **not yet saved**, so `fetch_history` sees only earlier messages and
   the question reaches the prompt exactly once — appended by `generate`.
4. Save `Message(role="user", content=message)` — whether or not step 3 succeeded.
5. On success: save `Message(role="assistant", content=reply)`; set `state.reply` and
   `state.retrieved_chunks` from the result (as `webhook.py` does); call
   `spawn_background_extractions(state, user.id)`; return `{"reply": ..., "model": ...}`.
6. If `run_agent` raises: the user message from step 4 is still saved (so the Access Log
   shows it), no reply is saved, return **502** `{"detail": str(exc)}`.

What the bot remembers per turn, from the existing `fetch_history`: the last 10 messages
(about 5 exchanges), the rolling conversation summary of older messages, favourites,
customer notes, and — once the precondition work is committed — recommendation history.

### `spawn_background_extractions`

The four `asyncio.create_task` blocks at the end of `process_telegram_message` in
`app/routers/webhook.py` (favourite, summarize, customer notes, recommendation) move into
`spawn_background_extractions(state: AgentState, user_id: int) -> None` in the same module.
Both the Telegram path and `POST /admin/chat` call it.

### `GET /admin/chat/history`

Returns the caller's most recent 50 messages, oldest first:
`[{"role": "user" | "assistant", "content": str, "created_at": str}]`.

### `DELETE /admin/chat/history`

Deletes the caller's `Message` rows and their `ConversationSummary` row. Keeps
`Favourite`, `CustomerNote` and `RecommendationHistory`. Returns 204.

### `AgentState.user_id`

Reverts from `int | None` to `int`; the stateless chat was the only `None` case.

## 4. Frontend

### Login page (`frontend/src/auth/LoginPage.tsx`)

- Login mode is unchanged: heading "Admin Login", "Sign in to manage the Matcha Bot",
  Username / Password, "Log in", redirect to `/panel/docs`.
- Below the button, a link-styled button "No account? Create one" switches to register mode.
- Register mode: heading "Create account", fields Username, Password, Confirm password,
  submit "Create account", and "Have an account? Log in" to switch back. Switching mode
  clears the error.
- If Password and Confirm password differ: error "Passwords do not match", no request.
- Server errors: 409 → "Username already taken"; 422 → "Username must be 3–32 characters
  (letters, numbers, _ . -) and password at least 8 characters"; anything else →
  "Registration failed".
- On success: sign in, then navigate to `/panel/chat`.
- Styling reuses the page's existing classes; the left illustration panel is unchanged.

### API client and auth context

- `client.ts`: `register(username, password): Promise<void>` — `POST /auth/register` with a
  JSON body and no `Authorization` header; a non-OK response throws `ApiError` with the
  status.
- `AuthContext`: adds `register(username, password)` which calls `register` then `login`.

### Chat page (`frontend/src/chat/ChatPage.tsx`)

- On mount, `GET /admin/chat/history` fills `messages`. Loaded assistant messages have no
  model, so their meta reads "Bot"; replies from this session keep "Bot · {model}".
- Send posts `{ message }` only.
- Reset calls `DELETE /admin/chat/history`, then clears the messages and error. A failed
  delete shows "Failed to reset the conversation" and keeps the messages.
- Next to Reset: "Clears the chat history. Remembered preferences stay."
- 403 and 502 responses show their `detail` in the existing `role="alert"` banner.

## 5. Testing

### Backend

- `tests/test_auth_register.py`:
  - 201 creates an account whose `password_hash` starts with `scrypt$` and does not contain
    the password.
  - 409 for an existing username and for the `.env` admin username.
  - 422 for a 2-character username, a username with a space, and a 7-character password.
  - An `account.register` audit entry is written.
- `tests/test_auth.py` additions: a registered account passes `require_admin` (e.g.
  `GET /admin/soul` returns 200); a wrong password returns 401; the `.env` admin still works;
  `verify_password` rejects a malformed stored value.
- `tests/test_admin_chat.py` rewritten, with `run_agent` and
  `spawn_background_extractions` monkeypatched in `app.routers.admin_chat`:
  - The first message creates the web channel and the `User`.
  - The `state.history` passed to `run_agent` does not contain the current message, and
    does contain an earlier exchange.
  - After a successful turn, one user and one assistant message are saved and
    `spawn_background_extractions` was called.
  - A blocked user gets 403 and `run_agent` is not called.
  - At the daily limit, the reply is `DAILY_LIMIT_REPLY` and `run_agent` is not called.
  - When `run_agent` raises: 502, the user message is saved, no assistant message.
  - `GET /admin/chat/history` returns only the caller's messages (two accounts).
  - `DELETE /admin/chat/history` removes the caller's messages and summary, keeps their
    favourites and customer notes, and leaves the other account's messages.
- `tests/test_admin_channels.py`: `GET /admin/channels` omits a `web` channel.
- `tests/test_webhook.py` passes after the `spawn_background_extractions` extraction.

### Frontend

- `tests/auth/LoginPage.test.tsx` additions: switching to register mode shows
  "Create account"; mismatched passwords show "Passwords do not match" without a request;
  a 409 shows "Username already taken"; success navigates to the Chat page.
- `tests/chat/ChatPage.test.tsx` rewritten: history loads on mount; send posts
  `{ message }` only; Reset calls `DELETE /admin/chat/history` and clears the conversation;
  the model badge, send-disabled and error tests stay.
- All other existing tests pass unmodified.

## 6. Implementation order

1. Backend: `Account` model + migration `0011`, `hash_password` / `verify_password`,
   `require_admin` accepting accounts, `POST /auth/register`, with tests.
2. Backend: `spawn_background_extractions` extraction; `get_web_user`; stateful
   `POST /admin/chat`, `GET` / `DELETE /admin/chat/history`; web channel hidden from the
   channel list; `AgentState.user_id` back to `int`; with tests.
3. Frontend: `register` in client and context, register mode on the login page, with tests.
4. Frontend: Chat page history and server-side reset, with tests.

## 7. Memory roadmap (follow-up specs)

The target is a four-tier memory architecture. Each step below gets its own spec → plan →
implementation, in this order, because each builds on the previous one:

| Step | Scope | Builds on |
|---|---|---|
| 1 | **This spec** — accounts + per-account chat memory using today's L0-style injection | — |
| 2 | Tier 1 — sessions, `SessionCompleted` event, Episodic Worker, Episodic Store (one summary per session); L0 injects recent episodes | 1 |
| 3 | Agent tool loop + L1 recall tools (`memory_search`, `memory_expand`) | 2 |
| 4 | Tier 0 — prune & compact by token budget (70% trim old tool results, 100% LLM summary into working history) | 3 |
| 5 | Tier 2 — Semantic Worker + Knowledge Graph + L2 `knowledge_graph_search`; Dreaming Worker (≥5 unprocessed episodes, 10-minute debounce) + Dreaming Doc | 2, 3 |

Nothing in this spec pre-builds for those steps.
