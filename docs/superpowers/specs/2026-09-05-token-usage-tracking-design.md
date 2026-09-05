# Token Usage Tracking — Design

## Context

The matcha/tea Telegram bot's agent pipeline (`backend/app/agent/nodes.py`) makes three
kinds of OpenAI calls per user turn:

- `retrieve()` — an embedding call (`text-embedding-3-small`) to search the knowledge base
- `generate()` — the main chat completion (`gpt-4o-mini`) that produces the bot's reply
- `extract_favourite()` — a background chat completion (`gpt-4o-mini`) that detects a
  favourite drink mention

None of these calls currently record how many tokens they consumed or which model served
them. The admin panel (`frontend/src/`) has no visibility into API cost or model usage.
This spec adds that visibility: a new `token_usage` table, a logging helper called from
each of the three call sites, two new admin API endpoints, and a new admin UI page.

This is additive only — no existing endpoint, route, or database table changes shape.

## Data Model

New table `token_usage` (new Alembic migration on top of the existing `0001_initial_tables`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `user_id` | Integer, FK → `users.id`, nullable | Null when the call isn't tied to a specific user (should not occur in practice today, since all three call sites run inside a per-user turn, but kept nullable for forward compatibility) |
| `call_type` | String | One of `"generate"`, `"extract_favourite"`, `"embedding"` |
| `model` | String | The exact model string passed to the OpenAI call (`"gpt-4o-mini"`, `"text-embedding-3-small"`) |
| `prompt_tokens` | Integer | From `response.usage.prompt_tokens` |
| `completion_tokens` | Integer, nullable | From `response.usage.completion_tokens`; null for embedding calls, which have no completion tokens |
| `total_tokens` | Integer | From `response.usage.total_tokens` |
| `created_at` | DateTime(timezone=True), default now (UTC) | |

Index on `created_at` (descending scans for the paginated list mirror the existing
`Message`/`AdminAuditLog` pattern).

SQLAlchemy model `TokenUsage` added to `backend/app/db/models.py`, following the existing
style in that file (`Mapped[...]` columns, no `__repr__` or extra methods beyond the
declarative mapping).

## Capture Points

New module `backend/app/token_usage.py` with one function:

```python
def log_token_usage(db: Session, user_id: int | None, call_type: str, model: str, usage) -> None:
```

`usage` is the OpenAI SDK's `Usage` object (or `None`, in which case the function is a
no-op — some mocked/test responses may not set it). The function builds a `TokenUsage` row
from `usage.prompt_tokens`, `getattr(usage, "completion_tokens", None)`, and
`usage.total_tokens`, adds it, and commits — mirroring the existing commit-per-write style
used elsewhere in `nodes.py` (e.g. `extract_favourite`'s `db.add(...); db.commit()`).

Called from three sites in `backend/app/agent/nodes.py`, immediately after each OpenAI
response is received:

- `retrieve()`: after the embedding call, `call_type="embedding"`, `model="text-embedding-3-small"`
- `generate()`: after the chat completion, `call_type="generate"`, `model=model` (the
  function's existing `model` parameter, default `"gpt-4o-mini"`)
- `extract_favourite()`: after its chat completion, `call_type="extract_favourite"`,
  `model=model` (same pattern as `generate`)

`extract_favourite()` already receives `db: Session`. Neither `retrieve()` nor
`generate()` does today — both gain a `db: Session` parameter. Both are wired in
`app/agent/graph.py`'s `build_graph(db, qdrant_client, openai_client)`, which already has
`db` in scope as its own parameter; the two node registration lines
(`graph.add_node("retrieve", lambda s: retrieve(s, qdrant_client, openai_client))` and
`graph.add_node("generate", lambda s: generate(s, openai_client))`) each simply gain `db`
as an argument. No change is needed in `webhook.py` or anywhere else upstream — these are
the only two changes to an existing function signature in this spec; everywhere else is
additive.

`log_token_usage` swallows its own failures internally (try/except around the row
construction and `db.add`/`db.commit`, calling `db.rollback()` in the except branch before
returning) rather than relying on each call site to wrap it. This matters beyond tidiness:
a `usage` object that isn't a real OpenAI SDK `Usage` (e.g. a bare `unittest.mock.MagicMock`
in a test that doesn't configure `.usage`, which yields `MagicMock` sub-objects instead of
ints) would otherwise raise inside `db.commit()` — and an uncaught error there leaves the
SQLAlchemy session in a failed-transaction state that breaks every later statement in the
same request/test until rolled back. Handling the rollback inside `log_token_usage` keeps
the three call sites a single plain call each: `log_token_usage(db, state.user_id,
"generate", model, response.usage)`, no `try/except` boilerplate at the call site.

Logging failures (e.g. a DB error while writing the usage row) must never break the
user-facing agent turn. `log_token_usage` calls are wrapped in a `try/except` at each
call site (matching the existing defensive style around `send_message`,
`send_chat_action`, and `extract_favourite`'s background task in `webhook.py`), logged via
`logger.exception(...)`, and swallowed.

## API

New router `backend/app/routers/admin_usage.py`, registered in `app/main.py` alongside
the other admin routers. Both endpoints require Basic Auth (same `Depends` pattern as
`admin_logs.py`) and both are read-only.

### `GET /admin/usage?limit=&offset=`

Paginated list, newest first — same shape and defaults (`limit` default 20, matching the
frontend's existing `PAGE_SIZE`) as `GET /admin/logs/access`. Response: 200, array of

```json
{
  "id": 1,
  "user_id": 42,
  "call_type": "generate",
  "model": "gpt-4o-mini",
  "prompt_tokens": 512,
  "completion_tokens": 128,
  "total_tokens": 640,
  "created_at": "2026-09-05T12:00:00"
}
```

### `GET /admin/usage/summary`

No parameters. Aggregates over the entire `token_usage` table. Response: 200,

```json
{
  "total_calls": 1234,
  "total_tokens": 987654,
  "estimated_cost_usd": 1.23,
  "by_model": [
    { "model": "gpt-4o-mini", "calls": 1000, "total_tokens": 900000, "estimated_cost_usd": 1.10 },
    { "model": "text-embedding-3-small", "calls": 234, "total_tokens": 87654, "estimated_cost_usd": 0.13 }
  ]
}
```

Cost is estimated server-side from a hardcoded price table in `admin_usage.py`
(USD per 1M tokens, current published OpenAI pricing at the time this spec is written):

| Model | Input (prompt) | Output (completion) |
|---|---|---|
| `gpt-4o-mini` | $0.15 | $0.60 |
| `text-embedding-3-small` | $0.02 | n/a (no completion tokens) |

A model not in this table contributes `0` to `estimated_cost_usd` for its rows (rather
than raising), so a future model change never breaks the summary endpoint — it just
undercounts cost until the price table is updated. This is a known, accepted limitation:
the estimate is for rough visibility, not billing reconciliation, and the frontend labels
it "Est. cost" to set that expectation.

## Frontend

New page `frontend/src/usage/UsagePage.tsx`, new route `/panel/usage` (added to `App.tsx`
alongside the other four `/panel/*` routes), new nav link "Usage" in `AppShell.tsx`.

Layout, top to bottom:

1. **Summary cards row** (4 cards, same `rounded-lg border border-border bg-card
   shadow-card` styling as the rest of the admin UI): Total Calls, Total Tokens, Est. Cost
   (USD, formatted `$X.XX`), and a "by model" card listing each model with its token count
   — reusing the existing card visual language, not a new component library.
2. **Detail table**, styled identically to `AccessLogPage.tsx`/`AuditLogPage.tsx`
   (same header/row/pagination classes, same loading/empty states): columns User (Telegram
   ID or "—" if null), Call Type, Model, Prompt, Completion, Total, When. Same
   Previous/Next pagination pattern (`PAGE_SIZE = 20`, `!error && entries.length <
   PAGE_SIZE` disables Next) as the existing log pages.

Both requests (`/admin/usage/summary` and `/admin/usage?limit=&offset=`) go through the
existing shared `apiFetch<T>` from `src/api/client.ts` — no new HTTP handling.

## Testing

**Backend** (`backend/tests/`):
- `test_token_usage.py`: `log_token_usage` writes a row with the right fields; a `None`
  usage is a no-op; a DB error during logging doesn't propagate (covers the try/except at
  a call site — test this at the `nodes.py` level, e.g. `generate()` still returns a reply
  when logging raises).
- `test_admin_usage.py`: `GET /admin/usage` returns paginated rows newest-first, matching
  the existing `test_admin_logs.py` pattern; `GET /admin/usage/summary` returns correct
  aggregates and cost for a small fixture set of rows, including a row with an
  unrecognized model (asserts it contributes 0 cost, not an error).
- Existing `retrieve()` tests in `test_agent_nodes.py` updated for the new `db` parameter.

**Frontend** (`frontend/tests/usage/UsagePage.test.tsx`): renders summary cards from a
mocked `/admin/usage/summary` response, renders detail rows from a mocked
`/admin/usage?limit=&offset=`, pagination Next/Previous behavior — mirroring
`AccessLogPage.test.tsx`'s test structure and MSW setup.

## Out of Scope

- Per-user or per-day usage breakdowns / charts (only the flat summary + paginated list
  described above).
- Rate limiting or budget alerts based on usage.
- Historical price-table versioning (if OpenAI pricing changes, the hardcoded table is
  edited in place — old rows are re-priced at the new rate on every summary computation,
  since cost is computed on read, not stored per-row).
