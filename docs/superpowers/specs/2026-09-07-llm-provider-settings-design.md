# LLM Provider Settings — Design

## Context

The bot's chat calls are hard-wired to OpenAI. `get_openai_client()`
(`backend/app/agent/clients.py`) builds one client from `OPENAI_API_KEY`, and the
model names live as module constants: `REWRITE_MODEL` and `RERANK_MODEL` in
`app/agent/nodes.py`, `CHUNK_MODEL` in `app/ingestion.py`, plus a
`model="gpt-4o-mini"` default on `generate` and `extract_favourite`. Changing any
of them means editing code and redeploying.

This spec adds a Settings page to the admin SPA that selects the LLM provider and
chat model for the bot's conversational calls, stored in the database and
changeable at runtime.

The agent nodes already accept their client as a parameter, so the seam exists.
The work is to decide what fills that parameter.

### Scope

**In scope:** provider and chat model for the four conversational call sites —
`rewrite_query`, `rerank`, `generate`, `extract_favourite` — plus the document
chunking call in `ingestion.py`, which is also a chat call. Providers: OpenAI and
Ollama.

**Out of scope, deliberately:**

- **Amazon Bedrock.** Deferred. See "What Bedrock will need" below so the next
  round does not have to re-investigate.
- **Changing the embedding provider.** Embeddings stay on OpenAI's
  `text-embedding-3-small`. The Chroma index was built with it; switching would
  invalidate every stored vector and require a full re-index behind a
  maintenance window.
- Per-`call_type` model selection. One `chat_model` serves all of them.
- Multiple saved configuration profiles.
- Per-channel provider selection.
- Per-provider pricing in Grafana. Ollama costing zero is correct, not a bug.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Providers | OpenAI, Ollama | Both speak the OpenAI wire protocol, so one client type serves both — only `base_url` and `api_key` differ. |
| Abstraction | None beyond a factory | Building a `ChatClient` protocol now would mean rewriting `nodes.py` against it today, for a provider that is deferred. The seam is a single function. |
| Config scope | One global row | The shop runs one bot. Metrics still split by model, so a switch stays visible. |
| Storage | New `llm_settings` table, singleton row | Explicit columns beat a key-value blob for five known fields. |
| Secret handling | AES-GCM via `app/crypto.py` | The same mechanism already protecting channel bot tokens. |
| Safety | Test before save, enforced in the UI | Mirrors the existing Channels page flow. |
| First run | Fall back to env at read time | No migration touches secrets, and deploying this changes no behaviour. |

## Data model

New table `llm_settings`, holding exactly one row (`id` is always 1, enforced by
`CHECK (id = 1)`).

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | Always 1 |
| `provider` | str | `"openai"` or `"ollama"` |
| `base_url` | str, nullable | `NULL` for OpenAI (SDK default); required for Ollama |
| `encrypted_api_key` | str, nullable | AES-GCM, via `app/crypto.py` |
| `chat_model` | str | Used by all five chat call sites |
| `updated_at` | datetime | |
| `updated_by` | str | Admin username |

Migration `0004_llm_settings` creates the table and inserts nothing. Downgrade
drops it. No backfill, no other table touched.

**Fallback.** With no row present, the system behaves exactly as it does today:
the client is built from `OPENAI_API_KEY` and the model is `gpt-4o-mini`. The
first save from the UI creates the row.

**The API key is never returned.** `GET` reports `has_api_key` as a boolean. The
UI shows an empty field labelled "saved — leave blank to keep", the same way
Channels handles bot tokens.

## Client resolution

`app/agent/clients.py` splits its single accessor into two, named for their roles:

```python
get_embedding_client()   # always OpenAI from env — the Chroma index depends on it
get_chat_client(db)      # reads llm_settings, returns OpenAI(api_key=..., base_url=...)
get_chat_model(db)       # reads llm_settings, returns the configured model name
```

`get_openai_client()` is removed with no compatibility alias, so no call site can
keep using one client for both purposes by accident.

This split is necessary, not cosmetic: today one client serves both roles.
`retrieve()` uses it for `_embed` and for `rewrite_query`/`rerank`
(`nodes.py`), and `admin_docs.py` passes the same client to `chunk_document`
(chat) and `embed_and_store` (embeddings).

`REWRITE_MODEL`, `RERANK_MODEL`, and `CHUNK_MODEL` are deleted. `EMBEDDING_MODEL`
stays.

### Signature changes

| Function | Before | After |
|---|---|---|
| `retrieve` | `(state, db, chroma_client, openai_client, ...)` | `(state, db, chroma_client, chat_client, embedding_client, chat_model, ...)` |
| `rewrite_query` | `(..., openai_client, db, user_id)` | `(..., chat_client, model, db, user_id)` |
| `rerank` | `(..., openai_client, db, user_id)` | `(..., chat_client, model, db, user_id)` |
| `generate` | `(state, db, openai_client, model="gpt-4o-mini", ...)` | `(state, db, chat_client, model, ...)` |
| `extract_favourite` | `(state, db, openai_client, model="gpt-4o-mini")` | `(state, db, chat_client, model)` |
| `build_graph` / `run_agent` | `(db, chroma_client, openai_client, on_delta)` | `(db, chroma_client, chat_client, embedding_client, chat_model, on_delta)` |
| `chunk_document` | `(text, filename, openai_client, db, user_id)` | `(text, filename, chat_client, chat_model, db, user_id)` |
| `embed_and_store` | `(..., openai_client, ...)` | `(..., embedding_client, ...)` |

Dropping the `model="gpt-4o-mini"` defaults is deliberate: the model must always
come from configuration, never silently from a constant.

Call sites to update: `app/routers/webhook.py` (two) and
`app/routers/admin_docs.py` (one, passing both clients).

### Caching

`get_chat_client` and `get_chat_model` cache in-process and are invalidated by
`invalidate_chat_client()`, called from `PUT /admin/llm-settings`. A provider
change takes effect on the next message with no restart.

**This is correct only because the backend runs a single uvicorn process**
(`backend/Dockerfile:15`, no `--workers`). Adding workers would leave each with
its own stale cache. This constraint must be restated as a comment at the cache
definition.

### Effect on metrics

Ollama returns `usage` over the OpenAI-compatible endpoint, so `log_token_usage`
and the token metrics keep working. `MODEL_PRICES` in `app/metrics.py` has no
Ollama entries, so `llm_cost_usd_total` stays at zero for them — correct, since a
self-hosted model has no per-token charge. The Grafana cost panel dropping to
zero after a switch is true information, and the Settings page says so before the
admin saves.

Some Ollama builds omit `usage` when streaming. `log_token_usage` already returns
early on `usage is None`, so nothing breaks; that turn simply records no tokens.

## Admin API

New router `app/routers/admin_llm_settings.py`, prefix `/admin/llm-settings`,
every route behind `Depends(require_admin)`, following `admin_channels.py`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/llm-settings` | Read the active configuration |
| POST | `/admin/llm-settings/test` | Try an unsaved configuration |
| PUT | `/admin/llm-settings` | Save |

**GET** returns:

```json
{
  "provider": "openai",
  "base_url": null,
  "chat_model": "gpt-4o-mini",
  "has_api_key": true,
  "is_default": false,
  "updated_at": "2026-09-07T10:00:00Z",
  "updated_by": "admin"
}
```

`is_default` is true when no row exists, so the UI can say which configuration
the admin is looking at. `api_key` never appears in a response.

**POST `/test`** takes the payload the UI is about to save and issues one cheap
chat call (`max_tokens=5`) against that provider, returning
`{"ok": true, "model": "llama3.1", "latency_ms": 340}` or
`{"ok": false, "error": "<trimmed provider message>"}`.

Three requirements at this endpoint:

- **Use a throwaway client.** Testing a broken configuration must not disturb the
  cached client currently serving customers.
- **Do not route through `retry_once`.** A test should fail fast, and must not
  inflate `llm_retries_total`.
- **Do not write `token_usage`.** This is an administrator's call, not a
  customer's; recording it would distort usage reporting.

If the payload's `api_key` is empty and a key is already stored, `/test` uses the
stored key, so an admin can change the model without re-entering the key.

**PUT** validates that `provider` is one of `openai` or `ollama`, that
`chat_model` is non-empty, and that `base_url` is present and a valid URL when the
provider is Ollama. It upserts row 1, encrypts `api_key` when one is supplied,
and calls `invalidate_chat_client()`.

It records an audit entry through the existing `log_admin_action`
(`app/auth.py`) with action `llm_settings.update`, detailing provider, base URL,
and chat model. **The API key never enters the audit log**, not even truncated.

**Where "test before save" is enforced.** In the UI only: Save unlocks after
`/test` returns `ok: true` and re-locks when any field changes. The backend keeps
no "tested" state — doing so would mean storing a server-side test token while
preventing no real failure, since any admin can call `PUT` directly. This is a
guard against mistakes, not a security boundary.

## Frontend

New file `src/settings/SettingsPage.tsx` — one page, one form, no sub-components.
Two files change: `src/App.tsx` gains the route, and `src/layout/AppShell.tsx`
gains a `Settings` link at the **end** of the sidebar, below Channels.

The page shows: a Provider dropdown; a Base URL field **visible only when Ollama
is selected**; an API key field; a Chat model field; a "Test connection" button
with its result; and a Save button.

Behaviour:

- The API key field always loads empty. When `has_api_key` is true it is
  annotated "saved — leave blank to keep". The key is never rendered, not even
  masked.
- Save is disabled until `/test` succeeds. **Any** subsequent edit — including a
  one-character change to the model — clears the test result and disables Save
  again, so a configuration can never be saved on the strength of a test of a
  different configuration.
- When `is_default` is true, a banner reads: "Using the default configuration
  from environment variables. Saving here overrides it." The form is pre-filled
  with `openai` / `gpt-4o-mini`.
- After a successful save the page re-reads from `GET`, so the admin sees what
  the server holds rather than what they typed.
- Switching to Ollama shows a note: Ollama has no per-token cost, so the cost
  chart will read zero.

**Ollama reachability.** The backend runs in a container, so `http://localhost:11434`
would point at the container itself. The Base URL placeholder is
`http://host.docker.internal:11434/v1`. When the Ollama server runs on a separate
host, its own URL applies and this caveat does not. `infra/README.md` gains a note
that on EC2 the Ollama server should live outside the instance — a `t3.small` has
no room for the stack and a model — and that the security group does not open
11434.

**Frontend tests** (`frontend/tests/settings/SettingsPage.test.tsx`): Save stays
disabled until a test succeeds; editing a field after a successful test disables
Save again; the Base URL field appears only for Ollama.

## Testing

| Area | Test |
|---|---|
| `get_chat_client` | Builds from env when unconfigured; honours `base_url` for Ollama; returns a fresh client after settings change (cache invalidated) |
| `get_chat_model` | Falls back to `gpt-4o-mini` when unconfigured; returns the stored model otherwise |
| Encryption | The stored key is not plaintext; it round-trips; saving with a blank key preserves the existing one |
| GET | No `api_key` field in the response; `has_api_key` and `is_default` correct in both states |
| POST `/test` | Reports success; reports a provider failure with a message; writes no `token_usage`; does not increment `llm_retries_total`; leaves the cached client untouched |
| PUT | Rejects an unknown provider, Ollama without `base_url`, and an empty `chat_model`; writes an audit entry; the audit entry contains no API key |
| Regression | The existing suite stays green after the signature changes |

Provider HTTP calls are stubbed with `respx`, already in the dev dependencies. No
test reaches the network.

Final manual check: point at the operator's Ollama server, exchange a message over
Telegram, then confirm in Grafana that `llm_tokens_total` carries the new model
label and `agent_node_duration_seconds` still records. This is the only step that
exercises the whole path.

## Risks

- **The signature change is broad.** Nine functions across three modules, plus
  three call sites.
  Mitigated by doing it as its own step, with the existing suite as the net, and
  by adding no behaviour in that step.
- **Small Ollama models ignore JSON mode.** `rerank` and `extract_favourite` pass
  `response_format={"type": "json_object"}`. Both already catch and fall back —
  `rerank` keeps retrieval order, `extract_favourite` returns early — so the bot
  degrades rather than breaks. Recorded here so it is not mistaken for a new bug.
- **Cache divergence under multiple workers.** In-process caching assumes one
  process; see the constraint above.
- **Ollama on the EC2 host.** A `t3.small` cannot host the stack and a model.

## What Bedrock will need

Recorded so the deferred work starts from an answer rather than a survey:

1. **`boto3` and IAM instead of an API key.** Credentials come from the instance
   role, not a stored secret, so the `encrypted_api_key` column does not apply and
   the Settings form needs a different shape for this provider (region, model id).
2. **A real adapter.** The Converse API differs from OpenAI's in message format,
   streaming envelope, and JSON-mode support. This is where the `ChatClient`
   protocol deferred in this spec gets built, with the OpenAI-compatible client as
   its first implementation.
3. **A usage translation layer.** Bedrock reports token counts in a different
   shape, so `log_token_usage` needs a small adapter before it can record them.

## Implementation order

1. Migration, the `LLMSettings` model, and the settings module (encryption,
   fallback, caching) — independently testable, with no consumers yet.
2. Split `get_chat_client` / `get_embedding_client`, change the signatures in the
   table above, update the three call sites. No new behaviour; the existing suite must stay
   green.
3. The `admin_llm_settings` router: GET, POST `/test`, PUT.
4. `SettingsPage.tsx`, the route, the sidebar link, and the frontend tests.
5. Update `README.md` and `infra/README.md`.
