# Token Usage Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every OpenAI API call the bot's agent pipeline makes (model, token counts) and expose it in the admin panel as a paginated log plus a cost-estimate summary.

**Architecture:** A new `token_usage` table and SQLAlchemy model; a single defensive `log_token_usage()` helper called from the three OpenAI call sites in `app/agent/nodes.py` (`retrieve`, `generate`, `extract_favourite`); two new read-only admin endpoints (`GET /admin/usage`, `GET /admin/usage/summary`); a new `UsagePage.tsx` admin panel page at `/panel/usage` styled identically to the existing log pages.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest (backend); React, TypeScript, Tailwind, Vitest + Testing Library + MSW (frontend).

**Spec:** `docs/superpowers/specs/2026-09-05-token-usage-tracking-design.md`

## Global Constraints

- Logging a usage row must never break the user-facing agent turn — `log_token_usage` catches all its own exceptions internally and calls `db.rollback()` before returning, so callers never need their own try/except around it.
- Cost is an estimate only, computed at read time from a hardcoded price table in `admin_usage.py`; a model not in that table contributes `$0` to the estimate rather than raising.
- `retrieve()` and `generate()` in `app/agent/nodes.py` both gain a new `db: Session` first-after-`state` parameter (matching `extract_favourite()`'s existing signature shape); `app/agent/graph.py`'s `build_graph()` already has `db` in scope and only needs its `retrieve`/`generate` node-registration lambdas updated — no change needed in `webhook.py`.
- All new frontend UI reuses the existing design tokens and classes already in the codebase (`bg-card`, `border-border`, `shadow-card`, `text-muted-foreground`, etc. from `tailwind.config.js`) — no new colors, fonts, or components introduced.
- Admin endpoints use the existing `require_admin` dependency from `app.auth` (HTTP Basic Auth), same as every other `/admin/*` route.

---

## File Structure

- `backend/migrations/versions/0002_token_usage.py` — new Alembic migration, creates `token_usage` table
- `backend/app/db/models.py` — add `TokenUsage` model (modify, append)
- `backend/app/token_usage.py` — new module, `log_token_usage()` helper
- `backend/tests/test_token_usage.py` — new, tests for the helper
- `backend/app/agent/nodes.py` — modify: `retrieve()` and `generate()` gain `db`, all three call sites call `log_token_usage()`
- `backend/app/agent/graph.py` — modify: pass `db` into `retrieve`/`generate` node lambdas
- `backend/tests/test_agent_nodes.py` — modify: update signatures of tests calling `retrieve()`/`generate()` to pass `db_session`
- `backend/app/routers/admin_usage.py` — new router, `GET /admin/usage` + `GET /admin/usage/summary`
- `backend/app/main.py` — modify: register the new router
- `backend/tests/test_admin_usage.py` — new, tests for both endpoints
- `frontend/src/usage/UsagePage.tsx` — new page
- `frontend/tests/usage/UsagePage.test.tsx` — new tests
- `frontend/src/App.tsx` — modify: add `/panel/usage` route
- `frontend/src/layout/AppShell.tsx` — modify: add "Usage" nav link

---

### Task 1: `TokenUsage` model + migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/migrations/versions/0002_token_usage.py`
- Test: `backend/tests/test_token_usage.py` (only the model-shape assertion; the helper itself is Task 2)

**Interfaces:**
- Consumes: `app.db.base.Base` (existing declarative base)
- Produces: `TokenUsage` SQLAlchemy model with columns `id`, `user_id`, `call_type`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `created_at` — this is what every later task imports from `app.db.models`.

- [ ] **Step 1: Add the `TokenUsage` model**

Append to `backend/app/db/models.py` (after the existing `AdminAuditLog` class, end of file):

```python
class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    call_type: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
```

No new imports are needed — `Integer`, `String`, `ForeignKey`, `DateTime`, `Mapped`, `mapped_column`, `Base`, and `_now` are already imported/defined at the top of this file for the other models.

- [ ] **Step 2: Write the migration**

Create `backend/migrations/versions/0002_token_usage.py`:

```python
"""token usage tracking

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("call_type", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("token_usage")
```

- [ ] **Step 3: Write a test that the table exists with the right shape**

Create `backend/tests/test_token_usage.py`:

```python
from app.db.models import TokenUsage


def test_token_usage_model_persists_all_fields(db_session):
    row = TokenUsage(
        user_id=None,
        call_type="embedding",
        model="text-embedding-3-small",
        prompt_tokens=10,
        completion_tokens=None,
        total_tokens=10,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id is not None
    assert row.user_id is None
    assert row.call_type == "embedding"
    assert row.model == "text-embedding-3-small"
    assert row.prompt_tokens == 10
    assert row.completion_tokens is None
    assert row.total_tokens == 10
    assert row.created_at is not None
```

- [ ] **Step 4: Run the test to verify it fails, then passes**

Run: `cd backend && python3.11 -m pytest tests/test_token_usage.py -v`
Expected before Step 1/2: FAIL with `ImportError: cannot import name 'TokenUsage'`
Expected after Step 1/2: PASS (the `db_session` fixture creates all tables via `Base.metadata.create_all`, so the Alembic migration doesn't need to run for this in-memory-SQLite test — it's exercised for real when the running app applies migrations, same as every other table in this codebase)

- [ ] **Step 5: Run the migration against the real dev database to confirm it applies cleanly**

Run: `cd backend && python3.11 -m alembic upgrade head`
Expected: `Running upgrade 0001 -> 0002, token usage tracking` with no errors

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/migrations/versions/0002_token_usage.py backend/tests/test_token_usage.py
git commit -m "feat(backend): add token_usage table and model"
```

---

### Task 2: `log_token_usage()` helper

**Files:**
- Create: `backend/app/token_usage.py`
- Test: `backend/tests/test_token_usage.py` (append to the file from Task 1)

**Interfaces:**
- Consumes: `app.db.models.TokenUsage` (Task 1)
- Produces: `log_token_usage(db: Session, user_id: int | None, call_type: str, model: str, usage) -> None` — this is the exact name and signature every call site in Task 3 uses.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_token_usage.py`:

```python
from app.db.models import TokenUsage
from app.token_usage import log_token_usage


class _FakeUsage:
    def __init__(self, prompt_tokens, total_tokens, completion_tokens=None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


def test_log_token_usage_writes_a_row_for_a_chat_call(db_session):
    usage = _FakeUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    log_token_usage(db_session, user_id=7, call_type="generate", model="gpt-4o-mini", usage=usage)

    rows = db_session.query(TokenUsage).all()
    assert len(rows) == 1
    assert rows[0].user_id == 7
    assert rows[0].call_type == "generate"
    assert rows[0].model == "gpt-4o-mini"
    assert rows[0].prompt_tokens == 100
    assert rows[0].completion_tokens == 50
    assert rows[0].total_tokens == 150


def test_log_token_usage_writes_null_completion_tokens_for_embedding_call(db_session):
    usage = _FakeUsage(prompt_tokens=20, total_tokens=20, completion_tokens=None)

    log_token_usage(db_session, user_id=None, call_type="embedding", model="text-embedding-3-small", usage=usage)

    row = db_session.query(TokenUsage).one()
    assert row.user_id is None
    assert row.completion_tokens is None
    assert row.total_tokens == 20


def test_log_token_usage_is_a_noop_when_usage_is_none(db_session):
    log_token_usage(db_session, user_id=1, call_type="generate", model="gpt-4o-mini", usage=None)

    assert db_session.query(TokenUsage).count() == 0


def test_log_token_usage_swallows_a_malformed_usage_object_and_leaves_session_usable(db_session):
    # An object with none of the expected attributes — simulates a test
    # double that didn't configure `.usage` at all.
    log_token_usage(db_session, user_id=1, call_type="generate", model="gpt-4o-mini", usage=object())

    assert db_session.query(TokenUsage).count() == 0
    # The session must still be usable afterward — a prior failed flush
    # left uncommitted/rolled-back, not the session itself broken.
    db_session.add(TokenUsage(user_id=1, call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1))
    db_session.commit()
    assert db_session.query(TokenUsage).count() == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python3.11 -m pytest tests/test_token_usage.py -v`
Expected: the four new tests FAIL with `ImportError: cannot import name 'log_token_usage'`

- [ ] **Step 3: Implement `log_token_usage`**

Create `backend/app/token_usage.py`:

```python
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import TokenUsage

logger = logging.getLogger(__name__)


def log_token_usage(db: Session, user_id: int | None, call_type: str, model: str, usage) -> None:
    """Persist one OpenAI call's token usage. Never raises.

    `usage` is the OpenAI SDK's response `.usage` object (or `None`, in
    which case this is a no-op). Any failure — a malformed `usage` object,
    a DB error — is logged and swallowed, with the session rolled back so
    it stays usable for the rest of the request.
    """
    if usage is None:
        return
    try:
        completion_tokens = getattr(usage, "completion_tokens", None)
        db.add(
            TokenUsage(
                user_id=user_id,
                call_type=call_type,
                model=model,
                prompt_tokens=int(usage.prompt_tokens),
                completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
                total_tokens=int(usage.total_tokens),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to log token usage for call_type=%s model=%s", call_type, model)
        db.rollback()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_token_usage.py -v`
Expected: all tests PASS (5 total: the Task 1 model test + 4 new ones)

- [ ] **Step 5: Commit**

```bash
git add backend/app/token_usage.py backend/tests/test_token_usage.py
git commit -m "feat(backend): add log_token_usage helper"
```

---

### Task 3: Wire `log_token_usage` into the agent pipeline

**Files:**
- Modify: `backend/app/agent/nodes.py`
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/tests/test_agent_nodes.py`

**Interfaces:**
- Consumes: `log_token_usage(db, user_id, call_type, model, usage)` (Task 2)
- Produces: `retrieve(state, db, qdrant_client, openai_client, ...)` and `generate(state, db, openai_client, ...)` — new signatures (db added as the parameter immediately after `state`) that Task 4 and any future caller must use. `extract_favourite`'s signature is unchanged.

- [ ] **Step 1: Update `retrieve()` and `generate()` in `nodes.py`, and call `log_token_usage` in all three functions**

In `backend/app/agent/nodes.py`, add the import at the top (alongside the existing imports):

```python
from app.token_usage import log_token_usage
```

Replace the `retrieve` function:

```python
def retrieve(
    state: AgentState,
    db: Session,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
    top_k: int = 5,
) -> AgentState:
    embedding_model = "text-embedding-3-small"
    response = retry_once(
        lambda: openai_client.embeddings.create(
            model=embedding_model,
            input=state.incoming_text,
        )
    )
    log_token_usage(db, state.user_id, "embedding", embedding_model, response.usage)
    embedding = response.data[0].embedding

    ensure_collection(qdrant_client, collection=collection)

    try:
        hits = retry_once(
            lambda: qdrant_client.search(collection_name=collection, query_vector=embedding, limit=top_k)
        )
    except Exception:
        # Tolerate a not-yet-existing (or otherwise unreachable) collection:
        # fall back to no retrieved context rather than failing the whole
        # agent turn.
        state.retrieved_chunks = []
        return state

    state.retrieved_chunks = [hit.payload.get("text", "") for hit in hits]
    return state
```

Replace the `generate` function:

```python
def generate(state: AgentState, db: Session, openai_client, model: str = "gpt-4o-mini") -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    messages.extend(state.history)
    messages.append({"role": "user", "content": state.incoming_text})

    response = retry_once(lambda: openai_client.chat.completions.create(model=model, messages=messages))
    log_token_usage(db, state.user_id, "generate", model, response.usage)
    state.reply = response.choices[0].message.content
    return state
```

In `extract_favourite`, add one line right after the existing `response = openai_client.chat.completions.create(...)` call (do not otherwise change this function):

```python
def extract_favourite(state: AgentState, db: Session, openai_client, model: str = "gpt-4o-mini") -> None:
    prompt = (
        "Extract whether the user expressed a favourite drink preference in this message. "
        'Respond with strict JSON: {"drink_name": "<name>"} or {"drink_name": null} if none. '
        f"Message: {state.incoming_text!r}"
    )
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    log_token_usage(db, state.user_id, "extract_favourite", model, response.usage)
    try:
        parsed = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return

    drink_name = parsed.get("drink_name")
    if not drink_name:
        return

    db.add(
        Favourite(
            user_id=state.user_id,
            drink_name=drink_name,
            confidence="inferred",
            source="chat",
        )
    )
    db.commit()
```

- [ ] **Step 2: Update `graph.py` to pass `db` into the `retrieve` and `generate` nodes**

In `backend/app/agent/graph.py`, replace the two node registration lines:

```python
    graph.add_node("retrieve", lambda s: retrieve(s, db, qdrant_client, openai_client))
    graph.add_node("generate", lambda s: generate(s, db, openai_client))
```

(The `fetch_history` line is unchanged — it already passes `db` the same way.)

- [ ] **Step 3: Update the existing tests that call `retrieve()` or `generate()` directly**

In `backend/tests/test_agent_nodes.py`, each of the following test functions needs `db_session` added as a parameter and `db=db_session` (or positional `db_session`) added to its call — the function bodies are otherwise unchanged. Apply this to all seven:

`test_retrieve_queries_qdrant_and_fills_chunks`, `test_retrieve_creates_collection_when_missing`,
`test_retrieve_tolerates_search_failure_and_returns_empty_chunks`,
`test_retrieve_retries_openai_embedding_once_then_succeeds`,
`test_generate_calls_openai_with_context_and_sets_reply`,
`test_generate_retries_openai_once_then_succeeds`,
`test_generate_propagates_when_both_attempts_fail`.

For example, `test_retrieve_queries_qdrant_and_fills_chunks` changes from:

```python
def test_retrieve_queries_qdrant_and_fills_chunks():
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    ...
    result = retrieve(state, qdrant_client=fake_qdrant, openai_client=fake_openai)
```

to:

```python
def test_retrieve_queries_qdrant_and_fills_chunks(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    ...
    result = retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)
```

Apply the same two changes (add `db_session` parameter, insert `db_session` as the second positional argument in the call) to the other six tests listed above. None of these tests configure `fake_openai`'s `.usage` attribute — that's fine: `log_token_usage` catches the resulting malformed-usage error internally (Task 2) and the tests' existing assertions on `result.reply` / `result.retrieved_chunks` are unaffected.

- [ ] **Step 4: Run the full agent test suite**

Run: `cd backend && python3.11 -m pytest tests/test_agent_nodes.py tests/test_token_usage.py tests/test_webhook.py -v`
Expected: all PASS. (`test_webhook.py` is included because it exercises `run_agent`/`build_graph` end-to-end through mocked `run_agent` — it should be unaffected, but it's the integration point that would break loudest if the `graph.py` wiring were wrong.)

- [ ] **Step 5: Run the full backend suite to catch anything else**

Run: `cd backend && python3.11 -m pytest -q`
Expected: all PASS, same count as before plus the new tests from Tasks 1–2.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/nodes.py backend/app/agent/graph.py backend/tests/test_agent_nodes.py
git commit -m "feat(backend): log token usage from retrieve/generate/extract_favourite"
```

---

### Task 4: Admin usage API endpoints

**Files:**
- Create: `backend/app/routers/admin_usage.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_usage.py`

**Interfaces:**
- Consumes: `app.db.models.TokenUsage` (Task 1), `app.auth.require_admin` (existing), `app.db.base.get_db` (existing)
- Produces: `GET /admin/usage` and `GET /admin/usage/summary` — the exact response shapes Task 5's frontend consumes.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_usage.py`:

```python
from app.db.models import TokenUsage


def test_usage_list_requires_auth(client):
    assert client.get("/admin/usage").status_code == 401


def test_usage_summary_requires_auth(client):
    assert client.get("/admin/usage/summary").status_code == 401


def test_usage_list_returns_rows_newest_first(client, db_session):
    db_session.add(TokenUsage(user_id=1, call_type="generate", model="gpt-4o-mini", prompt_tokens=10, completion_tokens=5, total_tokens=15))
    db_session.add(TokenUsage(user_id=1, call_type="embedding", model="text-embedding-3-small", prompt_tokens=3, total_tokens=3))
    db_session.commit()

    response = client.get("/admin/usage", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["call_type"] == "embedding"
    assert body[0]["completion_tokens"] is None
    assert body[1]["call_type"] == "generate"
    assert body[1]["completion_tokens"] == 5


def test_usage_list_respects_limit_and_offset(client, db_session):
    for i in range(3):
        db_session.add(TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=i, total_tokens=i))
    db_session.commit()

    response = client.get("/admin/usage?limit=1&offset=1", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_usage_summary_aggregates_totals_and_cost_by_model(client, db_session):
    db_session.add(TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000))
    db_session.add(TokenUsage(call_type="embedding", model="text-embedding-3-small", prompt_tokens=1_000_000, total_tokens=1_000_000))
    db_session.commit()

    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()

    assert body["total_calls"] == 2
    assert body["total_tokens"] == 2_000_000
    assert body["estimated_cost_usd"] == 0.17  # 0.15 (1M gpt-4o-mini prompt) + 0.02 (1M embedding)

    by_model = {row["model"]: row for row in body["by_model"]}
    assert by_model["gpt-4o-mini"]["calls"] == 1
    assert by_model["gpt-4o-mini"]["total_tokens"] == 1_000_000
    assert by_model["gpt-4o-mini"]["estimated_cost_usd"] == 0.15
    assert by_model["text-embedding-3-small"]["estimated_cost_usd"] == 0.02


def test_usage_summary_unknown_model_contributes_zero_cost(client, db_session):
    db_session.add(TokenUsage(call_type="generate", model="some-future-model", prompt_tokens=1_000_000, total_tokens=1_000_000))
    db_session.commit()

    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_cost_usd"] == 0.0
    assert body["by_model"][0]["estimated_cost_usd"] == 0.0


def test_usage_summary_with_no_rows(client, db_session):
    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body == {"total_calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "by_model": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python3.11 -m pytest tests/test_admin_usage.py -v`
Expected: FAIL with 404s (router doesn't exist yet) — every test fails.

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/admin_usage.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db.base import get_db
from app.db.models import TokenUsage

router = APIRouter(prefix="/admin/usage")

# USD per 1,000,000 tokens. A model not listed here contributes $0 to the
# cost estimate rather than raising — this is a rough-visibility estimate,
# not a billing reconciliation. Prices current as of this feature's design.
PRICES_PER_MILLION_TOKENS = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICES_PER_MILLION_TOKENS.get(model)
    if prices is None:
        return 0.0
    return (prompt_tokens * prices["prompt"] + completion_tokens * prices["completion"]) / 1_000_000


@router.get("")
def usage_list(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(TokenUsage)
        .order_by(TokenUsage.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "call_type": r.call_type,
            "model": r.model,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/summary")
def usage_summary(
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(
            TokenUsage.model,
            func.count(TokenUsage.id).label("calls"),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
        )
        .group_by(TokenUsage.model)
        .all()
    )

    by_model = []
    total_calls = 0
    total_tokens = 0
    estimated_cost_usd = 0.0
    for row in rows:
        cost = _estimate_cost_usd(row.model, row.prompt_tokens, row.completion_tokens)
        by_model.append(
            {
                "model": row.model,
                "calls": row.calls,
                "total_tokens": row.total_tokens,
                "estimated_cost_usd": round(cost, 4),
            }
        )
        total_calls += row.calls
        total_tokens += row.total_tokens
        estimated_cost_usd += cost

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost_usd, 4),
        "by_model": by_model,
    }
```

Note: `router = APIRouter(prefix="/admin/usage")` with a bare `@router.get("")` (not `@router.get("/")`) on the list endpoint is the correct FastAPI idiom to make the route exactly `/admin/usage` with no trailing slash — matching the existing `admin_docs.py` pattern (check `backend/app/routers/admin_docs.py` if unsure: it uses the same `router.get("")` shape for its collection-root endpoint).

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add the import and registration:

```python
from app.routers import admin_docs, admin_logs, admin_usage, admin_users, health, webhook
```

```python
app.include_router(admin_usage.router)
```

(Add this line after `app.include_router(admin_logs.router)`.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python3.11 -m pytest tests/test_admin_usage.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && python3.11 -m pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/admin_usage.py backend/app/main.py backend/tests/test_admin_usage.py
git commit -m "feat(backend): add /admin/usage list and summary endpoints"
```

---

### Task 5: Frontend `UsagePage`

**Files:**
- Create: `frontend/src/usage/UsagePage.tsx`
- Test: `frontend/tests/usage/UsagePage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

**Interfaces:**
- Consumes: `apiFetch<T>` from `frontend/src/api/client.ts` (existing); backend response shapes from Task 4 (`GET /admin/usage/summary` → `{total_calls, total_tokens, estimated_cost_usd, by_model: [{model, calls, total_tokens, estimated_cost_usd}]}`; `GET /admin/usage?limit=&offset=` → array of `{id, user_id, call_type, model, prompt_tokens, completion_tokens, total_tokens, created_at}`)
- Produces: `UsagePage(): JSX.Element`, mounted at `/panel/usage`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/usage/UsagePage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { UsagePage } from "../../src/usage/UsagePage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

const emptySummary = { total_calls: 0, total_tokens: 0, estimated_cost_usd: 0, by_model: [] };

describe("UsagePage", () => {
  it("renders the summary cards from the summary endpoint", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () =>
        HttpResponse.json({
          total_calls: 42,
          total_tokens: 123456,
          estimated_cost_usd: 1.2345,
          by_model: [{ model: "gpt-4o-mini", calls: 40, total_tokens: 120000, estimated_cost_usd: 1.1 }],
        })
      ),
      http.get(`${API_BASE}/admin/usage`, () => HttpResponse.json([]))
    );
    render(<UsagePage />);

    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("123456")).toBeInTheDocument();
    expect(screen.getByText("$1.2345")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
  });

  it("lists usage entries for the first page", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("20");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json([
          {
            id: 1,
            user_id: 7,
            call_type: "generate",
            model: "gpt-4o-mini",
            prompt_tokens: 100,
            completion_tokens: 50,
            total_tokens: 150,
            created_at: "now",
          },
        ]);
      })
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getByText("generate")).toBeInTheDocument());
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("requests the next page with an incremented offset", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, ({ request }) => {
        const url = new URL(request.url);
        const offset = url.searchParams.get("offset");
        if (offset === "0") {
          return HttpResponse.json(
            Array.from({ length: 20 }, (_, i) => ({
              id: i,
              user_id: 1,
              call_type: "generate",
              model: "gpt-4o-mini",
              prompt_tokens: i,
              completion_tokens: i,
              total_tokens: i * 2,
              created_at: "now",
            }))
          );
        }
        return HttpResponse.json([
          {
            id: 20,
            user_id: 1,
            call_type: "embedding",
            model: "text-embedding-3-small",
            prompt_tokens: 5,
            completion_tokens: null,
            total_tokens: 5,
            created_at: "now",
          },
        ]);
      })
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getAllByText("generate").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("embedding")).toBeInTheDocument());
  });

  it("shows an error message when the list fails to load", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, () => new HttpResponse(null, { status: 500 }))
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load usage"));
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- --run tests/usage/UsagePage.test.tsx`
Expected: FAIL with a module-not-found error (`UsagePage` doesn't exist yet).

- [ ] **Step 3: Implement `UsagePage.tsx`**

Create `frontend/src/usage/UsagePage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface UsageEntry {
  id: number;
  user_id: number | null;
  call_type: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number | null;
  total_tokens: number;
  created_at: string;
}

interface ModelBreakdown {
  model: string;
  calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

interface UsageSummary {
  total_calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
  by_model: ModelBreakdown[];
}

const PAGE_SIZE = 20;

const EMPTY_SUMMARY: UsageSummary = { total_calls: 0, total_tokens: 0, estimated_cost_usd: 0, by_model: [] };

export function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary>(EMPTY_SUMMARY);
  const [entries, setEntries] = useState<UsageEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<UsageSummary>("/admin/usage/summary")
      .then(setSummary)
      .catch(() => {
        /* summary is supplementary; the list's error banner is the primary signal */
      });
  }, []);

  async function load(currentOffset: number): Promise<void> {
    try {
      const data = await apiFetch<UsageEntry[]>(`/admin/usage?limit=${PAGE_SIZE}&offset=${currentOffset}`);
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load usage");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(offset);
  }, [offset]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Usage</h1>
        <p className="text-sm text-muted-foreground">OpenAI token usage and estimated cost.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total Calls</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summary.total_calls}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total Tokens</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summary.total_tokens}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Est. Cost</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">${summary.estimated_cost_usd}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">By Model</h2>
          <ul className="mt-1 flex flex-col gap-1">
            {summary.by_model.length === 0 ? (
              <li className="text-sm text-muted-foreground">No data yet</li>
            ) : (
              summary.by_model.map((m) => (
                <li key={m.model} className="text-sm text-foreground">
                  {m.model}: {m.total_tokens} tok
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full">
          <thead>
            <tr>
              <th>User</th>
              <th>Call Type</th>
              <th>Model</th>
              <th>Prompt</th>
              <th>Completion</th>
              <th>Total</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                  Loading usage…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                  No usage recorded yet.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="text-muted-foreground">{entry.user_id ?? "—"}</td>
                  <td>
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {entry.call_type}
                    </span>
                  </td>
                  <td className="font-medium text-foreground">{entry.model}</td>
                  <td>{entry.prompt_tokens}</td>
                  <td>{entry.completion_tokens ?? "—"}</td>
                  <td>{entry.total_tokens}</td>
                  <td className="text-muted-foreground">{entry.created_at}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex gap-2">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <button
          disabled={!error && entries.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- --run tests/usage/UsagePage.test.tsx`
Expected: all 4 tests PASS.

- [ ] **Step 5: Wire up the route and nav link**

In `frontend/src/App.tsx`, add the import:

```tsx
import { UsagePage } from "./usage/UsagePage";
```

and add the route inside the `/panel` route block, after `logs/audit`:

```tsx
            <Route path="usage" element={<UsagePage />} />
```

In `frontend/src/layout/AppShell.tsx`, add the nav link after "Audit Log":

```tsx
        <NavLink to="/panel/usage" className={linkClass}>
          Usage
        </NavLink>
```

- [ ] **Step 6: Run the full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: all tests PASS (the existing suite plus the 4 new `UsagePage` tests).

- [ ] **Step 7: Run the production build**

Run: `cd frontend && npm run build`
Expected: succeeds with no type errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/usage/UsagePage.tsx frontend/tests/usage/UsagePage.test.tsx frontend/src/App.tsx frontend/src/layout/AppShell.tsx
git commit -m "feat(frontend): add Usage admin page"
```

---

## Self-Review Notes

- **Spec coverage:** data model (Task 1), capture points including the `retrieve`/`generate` signature changes and the internal-rollback defensiveness (Tasks 2–3), both API endpoints including the unknown-model-cost-is-zero behavior (Task 4), frontend summary cards + detail table + pagination (Task 5), tests for every layer — all covered.
- **Type/name consistency check:** `log_token_usage(db, user_id, call_type, model, usage)` signature is identical across Task 2's implementation and every Task 3 call site. `TokenUsage` field names (`prompt_tokens`, `completion_tokens`, `total_tokens`, `call_type`, `model`, `user_id`, `created_at`) are identical across the model (Task 1), the helper (Task 2), the API response dict (Task 4), and the frontend `UsageEntry` interface (Task 5). The `/admin/usage/summary` response shape (`total_calls`, `total_tokens`, `estimated_cost_usd`, `by_model: [{model, calls, total_tokens, estimated_cost_usd}]`) matches between Task 4's implementation and Task 5's `UsageSummary`/`ModelBreakdown` interfaces and test fixtures.
- **Out of scope**, per the spec: per-user/per-day breakdowns or charts, rate limiting/budget alerts, historical price-table versioning. None of the tasks above build any of these.
