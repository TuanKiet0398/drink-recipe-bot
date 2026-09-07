# LLM Provider Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin choose the LLM provider (OpenAI or Ollama) and chat model for the bot's conversational calls from a Settings page, stored in the database and effective without a restart.

**Architecture:** OpenAI and Ollama speak the same wire protocol, so a single factory reads a one-row `llm_settings` table and returns a configured `OpenAI` client. Embeddings stay pinned to OpenAI because the Chroma index depends on `text-embedding-3-small`, which forces the existing single client to split into `get_chat_client(db)` and `get_embedding_client()`. The admin API mirrors the existing Channels flow: test an unsaved configuration, then save.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy + Alembic, the `openai` SDK, `respx` for HTTP stubbing, React + TypeScript + Vite, Vitest + Testing Library + msw.

**Spec:** `docs/superpowers/specs/2026-09-07-llm-provider-settings-design.md`

## Global Constraints

- Python floor is `>=3.11` (`backend/pyproject.toml`). Ruff is configured with `line-length = 110`, `target-version = "py311"`, `select = ["E", "F", "I", "UP", "B"]`. Run `ruff check . && ruff format --check .` in `backend/` before every commit.
- Backend tests run from `backend/`: `OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest -q`. Both env vars must be set or collection fails.
- Frontend tests run from `frontend/`: `npm run test` (Vitest). **Two tests fail before this work starts** — `tests/welcome/WelcomePage.test.tsx` and `tests/App.test.tsx`, both from `getByRole("link", { name: "Enter Admin Panel" })` matching multiple elements. They are pre-existing and out of scope. Do not fix them, and do not treat them as regressions.
- Providers are exactly `"openai"` and `"ollama"`. No others.
- **The API key is never returned by any endpoint, never written to the audit log, and never rendered in the UI — not even masked.**
- Embeddings always use OpenAI with `text-embedding-3-small` from `OPENAI_API_KEY`, regardless of the chat provider. Never route an embedding call through the configured chat client.
- In-process caching of the chat client is correct **only** because the backend runs a single uvicorn process (`backend/Dockerfile:15`, no `--workers`). This constraint must appear as a comment at the cache definition.
- Existing helpers to reuse, not reinvent: `app/crypto.py` `encrypt(plaintext) -> str` / `decrypt(ciphertext) -> str`; `app/auth.py` `log_admin_action(db, action, target="", ip="") -> None` and `require_admin`; `app/db/models.py` `_now()` for UTC timestamp defaults.

---

### Task 1: Settings model, migration, and the settings module

**Files:**
- Create: `backend/migrations/versions/0004_llm_settings.py`
- Create: `backend/app/llm_settings.py`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_llm_settings.py`

**Interfaces:**
- Consumes: `app.crypto.encrypt` / `decrypt`; `app.db.models._now`.
- Produces:
  - `app.db.models.LLMSettings` — SQLAlchemy model, table `llm_settings`
  - `app.llm_settings.DEFAULT_CHAT_MODEL: str` = `"gpt-4o-mini"`
  - `app.llm_settings.PROVIDERS: tuple[str, ...]` = `("openai", "ollama")`
  - `app.llm_settings.ResolvedSettings` — a frozen dataclass with fields `provider: str`, `base_url: str | None`, `api_key: str`, `chat_model: str`, `is_default: bool`
  - `app.llm_settings.resolve(db) -> ResolvedSettings`
  - `app.llm_settings.save(db, provider, base_url, api_key, chat_model, updated_by) -> LLMSettings` — `api_key=None` keeps any stored key
  - `app.llm_settings.read_row(db) -> LLMSettings | None`

- [ ] **Step 1: Add the model**

In `backend/app/db/models.py`, append:

```python
class LLMSettings(Base):
    """Singleton row (id is always 1) holding the active chat provider.

    Embeddings are deliberately not represented here: the Chroma index is
    built with OpenAI's text-embedding-3-small, so changing that provider
    would invalidate every stored vector.
    """

    __tablename__ = "llm_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_llm_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    chat_model: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    updated_by: Mapped[str] = mapped_column(String, default="")
```

Extend the existing SQLAlchemy import line to include `CheckConstraint`:

```python
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
```

- [ ] **Step 2: Write the migration**

Create `backend/migrations/versions/0004_llm_settings.py`:

```python
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
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_llm_settings.py`:

```python
import pytest

from app import llm_settings
from app.db.models import LLMSettings


def test_resolve_falls_back_to_the_environment_when_unconfigured(db_session):
    resolved = llm_settings.resolve(db_session)

    assert resolved.provider == "openai"
    assert resolved.base_url is None
    assert resolved.chat_model == llm_settings.DEFAULT_CHAT_MODEL
    assert resolved.is_default is True
    # conftest sets OPENAI_API_KEY for the whole suite
    assert resolved.api_key != ""


def test_save_creates_the_singleton_row(db_session):
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key="secret-key",
        chat_model="llama3.1",
        updated_by="admin",
    )

    rows = db_session.query(LLMSettings).all()
    assert len(rows) == 1
    assert rows[0].id == 1


def test_save_twice_updates_rather_than_inserting(db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="k1", chat_model="gpt-4o-mini", updated_by="admin"
    )
    llm_settings.save(
        db_session, provider="ollama", base_url="http://x:11434/v1", api_key="k2", chat_model="llama3.1", updated_by="admin"
    )

    rows = db_session.query(LLMSettings).all()
    assert len(rows) == 1
    assert rows[0].provider == "ollama"


def test_resolve_returns_the_stored_configuration(db_session):
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key="secret-key",
        chat_model="llama3.1",
        updated_by="admin",
    )

    resolved = llm_settings.resolve(db_session)

    assert resolved.provider == "ollama"
    assert resolved.base_url == "http://ollama.local:11434/v1"
    assert resolved.api_key == "secret-key"
    assert resolved.chat_model == "llama3.1"
    assert resolved.is_default is False


def test_the_api_key_is_encrypted_at_rest(db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="sk-plaintext", chat_model="gpt-4o-mini", updated_by="admin"
    )

    stored = db_session.query(LLMSettings).one().encrypted_api_key
    assert stored is not None
    assert "sk-plaintext" not in stored


def test_saving_with_no_key_keeps_the_stored_one(db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="sk-original", chat_model="gpt-4o-mini", updated_by="admin"
    )

    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key=None, chat_model="gpt-4o", updated_by="admin"
    )

    resolved = llm_settings.resolve(db_session)
    assert resolved.api_key == "sk-original"
    assert resolved.chat_model == "gpt-4o"


def test_an_ollama_row_with_no_key_resolves_to_an_empty_key(db_session):
    # Ollama needs no credentials; the SDK still requires a non-None api_key,
    # so an empty string is the resolved value and the client factory
    # substitutes a placeholder.
    llm_settings.save(
        db_session, provider="ollama", base_url="http://x:11434/v1", api_key=None, chat_model="llama3.1", updated_by="admin"
    )

    assert llm_settings.resolve(db_session).api_key == ""


def test_read_row_returns_none_when_unconfigured(db_session):
    assert llm_settings.read_row(db_session) is None


def test_providers_are_exactly_openai_and_ollama():
    assert llm_settings.PROVIDERS == ("openai", "ollama")
```

- [ ] **Step 4: Run the tests to verify they fail**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_llm_settings.py -q
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm_settings'`

- [ ] **Step 5: Write the settings module**

Create `backend/app/llm_settings.py`:

```python
"""Reading and writing the active LLM chat configuration.

This module owns the fallback rule: with no row in `llm_settings`, the
system behaves exactly as it did before the table existed — the chat client
is built from OPENAI_API_KEY with the default model.

Embeddings are not configurable here. See `app.agent.clients`.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import decrypt, encrypt
from app.db.models import LLMSettings

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
PROVIDERS = ("openai", "ollama")

_SINGLETON_ID = 1


@dataclass(frozen=True)
class ResolvedSettings:
    provider: str
    base_url: str | None
    api_key: str
    chat_model: str
    is_default: bool


def read_row(db: Session) -> LLMSettings | None:
    return db.query(LLMSettings).filter_by(id=_SINGLETON_ID).one_or_none()


def resolve(db: Session) -> ResolvedSettings:
    row = read_row(db)
    if row is None:
        return ResolvedSettings(
            provider="openai",
            base_url=None,
            api_key=get_settings().openai_api_key,
            chat_model=DEFAULT_CHAT_MODEL,
            is_default=True,
        )
    return ResolvedSettings(
        provider=row.provider,
        base_url=row.base_url,
        api_key=decrypt(row.encrypted_api_key) if row.encrypted_api_key else "",
        chat_model=row.chat_model,
        is_default=False,
    )


def save(
    db: Session,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    chat_model: str,
    updated_by: str,
) -> LLMSettings:
    """Upsert the singleton row.

    `api_key=None` means "leave the stored key alone", which is how the UI
    lets an admin change the model without re-entering the key.
    """
    row = read_row(db)
    if row is None:
        row = LLMSettings(id=_SINGLETON_ID, provider=provider, chat_model=chat_model)
        db.add(row)

    row.provider = provider
    row.base_url = base_url
    row.chat_model = chat_model
    row.updated_by = updated_by
    if api_key is not None:
        row.encrypted_api_key = encrypt(api_key) if api_key else None

    db.commit()
    db.refresh(row)
    return row
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_llm_settings.py -q
```
Expected: PASS, 9 tests.

- [ ] **Step 7: Verify the migration runs on a real database**

```bash
cd backend && rm -f /tmp/llm-mig-check.db
DATABASE_URL=sqlite:////tmp/llm-mig-check.db OPENAI_API_KEY=x ENCRYPTION_KEY=***REMOVED*** alembic upgrade head
DATABASE_URL=sqlite:////tmp/llm-mig-check.db OPENAI_API_KEY=x ENCRYPTION_KEY=***REMOVED*** alembic downgrade 0003
rm -f /tmp/llm-mig-check.db
```
Expected: both commands exit 0. Upgrade must show `0003 -> 0004`.

- [ ] **Step 8: Lint and commit**

```bash
cd backend && ruff check . && ruff format --check .
git add backend/app/llm_settings.py backend/app/db/models.py backend/migrations/versions/0004_llm_settings.py backend/tests/test_llm_settings.py
git commit -m "feat: add llm_settings table and settings resolution"
```

---

### Task 2: Split the chat and embedding clients

**Files:**
- Modify: `backend/app/agent/clients.py`
- Test: `backend/tests/test_agent_clients.py`

**Interfaces:**
- Consumes: `app.llm_settings.resolve`, `ResolvedSettings`, `DEFAULT_CHAT_MODEL` from Task 1.
- Produces:
  - `get_embedding_client() -> OpenAI` — always built from `OPENAI_API_KEY`
  - `get_chat_client(db) -> OpenAI` — built from `llm_settings`
  - `get_chat_model(db) -> str`
  - `build_chat_client(provider: str, base_url: str | None, api_key: str) -> OpenAI` — no DB access, used by the test endpoint in Task 4
  - `invalidate_chat_client() -> None`
  - `get_chroma_client()` and `get_or_create_collection()` keep their current signatures.
- Removes: `get_openai_client()`. Task 3 updates every caller.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_agent_clients.py`:

```python
def test_get_embedding_client_uses_the_environment_key():
    from app.agent.clients import get_embedding_client

    client = get_embedding_client()

    assert client.api_key == "test-key-not-real"


def test_get_chat_client_falls_back_to_the_environment(db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    client = get_chat_client(db_session)

    assert client.api_key == "test-key-not-real"


def test_get_chat_client_honours_a_configured_base_url(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_client, invalidate_chat_client

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    client = get_chat_client(db_session)

    assert str(client.base_url).rstrip("/") == "http://ollama.local:11434/v1"


def test_get_chat_client_is_cached_until_invalidated(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    first = get_chat_client(db_session)
    assert get_chat_client(db_session) is first

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    assert get_chat_client(db_session) is not first


def test_get_chat_model_falls_back_to_the_default(db_session):
    from app.agent.clients import get_chat_model, invalidate_chat_client

    invalidate_chat_client()

    assert get_chat_model(db_session) == "gpt-4o-mini"


def test_get_chat_model_returns_the_configured_model(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_model, invalidate_chat_client

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://x:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    assert get_chat_model(db_session) == "llama3.1"


def test_build_chat_client_substitutes_a_placeholder_key_for_ollama():
    from app.agent.clients import build_chat_client

    client = build_chat_client("ollama", "http://x:11434/v1", "")

    # The OpenAI SDK refuses an empty api_key, and Ollama ignores it.
    assert client.api_key == "ollama"


def test_get_openai_client_is_gone():
    import app.agent.clients as clients

    assert not hasattr(clients, "get_openai_client")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_agent_clients.py -q
```
Expected: FAIL — `cannot import name 'get_embedding_client'`

- [ ] **Step 3: Rewrite the clients module**

Replace `backend/app/agent/clients.py`:

```python
from functools import lru_cache

from chromadb import PersistentClient
from openai import OpenAI
from sqlalchemy.orm import Session

from app import llm_settings
from app.config import get_settings

# The chat client and model are cached across requests and cleared by
# invalidate_chat_client() when settings change, so a provider switch takes
# effect on the next message without a restart.
#
# This is correct ONLY because the backend runs a single uvicorn process
# (see backend/Dockerfile — no --workers). With more than one worker each
# would hold its own stale copy and a save would take effect unevenly.
_chat_cache: dict[str, object] = {}


@lru_cache
def get_embedding_client() -> OpenAI:
    """Embeddings always go to OpenAI.

    The Chroma index is built with text-embedding-3-small; routing this
    through the configured chat provider would invalidate every vector.
    """
    return OpenAI(api_key=get_settings().openai_api_key)


def build_chat_client(provider: str, base_url: str | None, api_key: str) -> OpenAI:
    """Construct a chat client from explicit values, without touching the DB
    or the cache. Used both by get_chat_client and by the settings test
    endpoint, which must never disturb the client serving customers."""
    # The SDK rejects an empty api_key. Ollama ignores whatever is sent, so a
    # placeholder keeps a credential-free provider working.
    if not api_key and provider == "ollama":
        api_key = "ollama"
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def invalidate_chat_client() -> None:
    _chat_cache.clear()


def _resolved(db: Session) -> llm_settings.ResolvedSettings:
    cached = _chat_cache.get("resolved")
    if cached is None:
        cached = llm_settings.resolve(db)
        _chat_cache["resolved"] = cached
    return cached  # type: ignore[return-value]


def get_chat_client(db: Session) -> OpenAI:
    client = _chat_cache.get("client")
    if client is None:
        resolved = _resolved(db)
        client = build_chat_client(resolved.provider, resolved.base_url, resolved.api_key)
        _chat_cache["client"] = client
    return client  # type: ignore[return-value]


def get_chat_model(db: Session) -> str:
    return _resolved(db).chat_model


@lru_cache
def get_chroma_client() -> PersistentClient:
    settings = get_settings()
    return PersistentClient(path=settings.chroma_persist_dir)


def get_or_create_collection(chroma_client, name: str = "matcha_knowledge"):
    """Idempotently get (or create) `name`, configured for cosine distance so
    `1 - distance` matches the cosine-similarity score semantics the rest of
    the codebase already assumes (previously provided by Qdrant's
    `Distance.COSINE`)."""
    return chroma_client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_agent_clients.py tests/test_llm_settings.py -q
```
Expected: PASS. The rest of the suite is expected to be red at this point — Task 3 fixes the callers.

- [ ] **Step 5: Commit**

`ruff` must pass, but do not run the whole suite yet; `get_openai_client` still has callers.

```bash
cd backend && ruff check . && ruff format --check .
git add backend/app/agent/clients.py backend/tests/test_agent_clients.py
git commit -m "feat: split the chat client from the embedding client"
```

---

### Task 3: Thread the chat client and model through the call sites

**Files:**
- Modify: `backend/app/agent/nodes.py`
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/ingestion.py`
- Modify: `backend/app/routers/webhook.py`
- Modify: `backend/app/routers/admin_docs.py`
- Test: `backend/tests/test_agent_nodes.py`, `backend/tests/test_agent_graph.py`, `backend/tests/test_ingestion.py`, `backend/tests/test_webhook.py`, `backend/tests/test_admin_docs.py`

**Interfaces:**
- Consumes: `get_chat_client(db)`, `get_embedding_client()`, `get_chat_model(db)` from Task 2.
- Produces: the signatures in the table below. No new behaviour.

This task adds nothing. Its whole deliverable is that the existing suite is green again with the model coming from configuration. Do not change any logic.

| Function | New signature |
|---|---|
| `rewrite_query` | `(question, history, chat_client, model, db, user_id)` |
| `rerank` | `(question, chunks, chat_client, model, db, user_id)` |
| `retrieve` | `(state, db, chroma_client, chat_client, embedding_client, chat_model, collection="matcha_knowledge", retrieval_k=10, final_k=5, score_threshold=0.50)` |
| `generate` | `(state, db, chat_client, model, on_delta=None)` |
| `extract_favourite` | `(state, db, chat_client, model)` |
| `build_graph` | `(db, chroma_client, chat_client, embedding_client, chat_model, on_delta=None)` |
| `run_agent` | `(state, db, chroma_client, chat_client, embedding_client, chat_model, on_delta=None)` |
| `_chunk_via_llm` | `(text, filename, chat_client, chat_model, db, user_id)` |
| `chunk_document` | `(text, filename, chat_client, chat_model, db, user_id=None)` |
| `embed_and_upsert` | `(chunks, filename, document_id, chroma_client, embedding_client)` |

- [ ] **Step 1: Update `nodes.py`**

Delete the constants `REWRITE_MODEL` and `RERANK_MODEL`. Keep `EMBEDDING_MODEL`.

`rewrite_query` — change the signature and the two `model=` uses:

```python
def rewrite_query(
    question: str, history: list[dict], chat_client, model: str, db: Session, user_id: int | None
) -> str:
```
Inside it, `_call` becomes `chat_client.chat.completions.create(model=model, ...)`, the retry becomes `retry_once(_call, call_type="rewrite_query", model=model)`, and the logging line becomes `log_token_usage(db, user_id, "rewrite_query", model, response.usage)`.

`rerank` — the same shape:

```python
def rerank(
    question: str, chunks: list[str], chat_client, model: str, db: Session, user_id: int | None
) -> list[str]:
```
with `chat_client.chat.completions.create(model=model, ...)`, `retry_once(_call, call_type="rerank", model=model)`, and `log_token_usage(db, user_id, "rerank", model, response.usage)`.

`retrieve` — new parameters, and the two inner calls now pass the right client:

```python
def retrieve(
    state: AgentState,
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    collection: str = "matcha_knowledge",
    retrieval_k: int = 10,
    final_k: int = 5,
    score_threshold: float = 0.50,
) -> AgentState:
    def _embed(text: str) -> list[float]:
        response = retry_once(
            lambda: embedding_client.embeddings.create(model=EMBEDDING_MODEL, input=text),
            call_type="embedding",
            model=EMBEDDING_MODEL,
        )
        log_token_usage(db, state.user_id, "embedding", EMBEDDING_MODEL, response.usage)
        return response.data[0].embedding
```
and further down:

```python
        rewritten = rewrite_query(
            state.incoming_text, state.history, chat_client, chat_model, db, state.user_id
        )
```
```python
    state.retrieved_chunks = rerank(
        state.incoming_text, merged, chat_client, chat_model, db, state.user_id
    )[:final_k]
```

`generate` and `extract_favourite` — drop the defaults and rename the client:

```python
def generate(
    state: AgentState,
    db: Session,
    chat_client,
    model: str,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
```
```python
def extract_favourite(state: AgentState, db: Session, chat_client, model: str) -> None:
```
Inside both, replace `openai_client` with `chat_client`.

- [ ] **Step 2: Update `graph.py`**

```python
def build_graph(
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    on_delta: Callable[[str], None] | None = None,
):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", _timed("fetch_history", lambda s: fetch_history(s, db)))
    graph.add_node(
        "retrieve",
        _timed(
            "retrieve",
            lambda s: retrieve(s, db, chroma_client, chat_client, embedding_client, chat_model),
        ),
    )
    graph.add_node(
        "generate",
        _timed("generate", lambda s: generate(s, db, chat_client, chat_model, on_delta=on_delta)),
    )

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(
    state: AgentState,
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    compiled = build_graph(db, chroma_client, chat_client, embedding_client, chat_model, on_delta=on_delta)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
```

- [ ] **Step 3: Update `ingestion.py`**

Delete the `CHUNK_MODEL` constant. Keep `EMBEDDING_MODEL`.

```python
def _chunk_via_llm(text: str, filename: str, chat_client, chat_model: str, db, user_id: int | None) -> list[Chunk]:
```
with `chat_client.chat.completions.create(model=chat_model, ...)` and the `log_token_usage` call passing `chat_model` where it passed `CHUNK_MODEL`.

```python
def chunk_document(text: str, filename: str, chat_client, chat_model: str, db, user_id: int | None = None) -> list[Chunk]:
```
whose body calls `_chunk_via_llm(text, filename, chat_client, chat_model, db, user_id)`.

```python
def embed_and_upsert(
    chunks,
    filename: str,
    document_id: int,
    chroma_client,
    embedding_client,
):
```
with the embedding call reading `embedding_client.embeddings.create(model=EMBEDDING_MODEL, input=text)`.

- [ ] **Step 4: Update `webhook.py`**

Replace the import:

```python
from app.agent.clients import get_chat_client, get_chat_model, get_chroma_client, get_embedding_client
```

The `run_agent` call becomes:

```python
        result = await asyncio.to_thread(
            run_agent,
            state,
            db=db,
            chroma_client=get_chroma_client(),
            chat_client=get_chat_client(db),
            embedding_client=get_embedding_client(),
            chat_model=get_chat_model(db),
            on_delta=deliverer.on_delta,
        )
```

`_extract_favourite_background` opens its own session, so it resolves the client from that session:

```python
async def _extract_favourite_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_favourite makes a blocking OpenAI call; run it off the
        # event loop thread so it doesn't stall other concurrent requests.
        await asyncio.to_thread(
            extract_favourite,
            state,
            db=db,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("extract_favourite failed for user_id=%s", user_id)
    finally:
        db.close()
```

- [ ] **Step 5: Update `admin_docs.py`**

```python
from app.agent.clients import (
    get_chat_client,
    get_chat_model,
    get_chroma_client,
    get_embedding_client,
    get_or_create_collection,
)
```
```python
    text = raw.decode("utf-8", errors="ignore")
    chunks = chunk_document(
        text, filename, chat_client=get_chat_client(db), chat_model=get_chat_model(db), db=db
    )
```
```python
    embed_and_upsert(
        chunks=chunks,
        filename=filename,
        document_id=doc.id,
        chroma_client=get_chroma_client(),
        embedding_client=get_embedding_client(),
    )
```

Check the rest of `admin_docs.py` for other `get_openai_client()` or `get_or_create_collection` uses (the delete path also touches Chroma) and update any that reference the removed function.

- [ ] **Step 6: Update the existing tests**

The existing tests pass `openai_client=` by keyword. Update each call to the new parameter names. Search for what needs changing:

```bash
cd backend && grep -rn "openai_client\|run_agent\|build_graph\|chunk_document\|embed_and_upsert\|rewrite_query\|rerank(" tests/
```

Rules for the edit: a chat call site takes `chat_client=<mock>, model=<"gpt-4o-mini">` (or `chat_model=` where the table above says so); an embedding call site takes `embedding_client=<mock>`. Where a test previously passed one mock for both, `retrieve` and `run_agent` now need both parameters — pass the same mock to both unless the test asserts on which client was used.

Do not weaken any assertion to make a test pass. If an assertion no longer holds, the production change is wrong.

- [ ] **Step 7: Run the whole suite**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest -q
```
Expected: PASS, no failures. This is the gate for the task — the count must be at least the 153 tests that passed before, plus the tests added in Tasks 1 and 2.

- [ ] **Step 8: Confirm no caller of the removed function survives**

```bash
cd backend && ! grep -rn "get_openai_client" app/ tests/ && echo "no references"
```
Expected: prints `no references`.

- [ ] **Step 9: Lint and commit**

```bash
cd backend && ruff check . && ruff format --check .
git add backend/app backend/tests
git commit -m "refactor: resolve the chat client and model from settings at every call site"
```

---

### Task 4: Admin API for reading, testing, and saving settings

**Files:**
- Create: `backend/app/routers/admin_llm_settings.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_llm_settings.py`

**Interfaces:**
- Consumes: `llm_settings.resolve/save/read_row/PROVIDERS/DEFAULT_CHAT_MODEL` (Task 1); `build_chat_client`, `invalidate_chat_client` (Task 2); `require_admin`, `log_admin_action` (existing).
- Produces: `GET`, `POST /test`, and `PUT` at `/admin/llm-settings`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_llm_settings.py`:

```python
import httpx
import respx

from app import llm_settings
from app.db.models import AdminAuditLog

AUTH = ("admin", "admin")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OLLAMA_CHAT_URL = "http://ollama.local:11434/v1/chat/completions"

CHAT_OK = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o-mini",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


def test_endpoints_require_auth(client):
    assert client.get("/admin/llm-settings").status_code == 401
    assert client.put("/admin/llm-settings", json={}).status_code == 401
    assert client.post("/admin/llm-settings/test", json={}).status_code == 401


def test_get_reports_the_default_when_unconfigured(client):
    body = client.get("/admin/llm-settings", auth=AUTH).json()

    assert body["is_default"] is True
    assert body["provider"] == "openai"
    assert body["chat_model"] == "gpt-4o-mini"
    assert body["has_api_key"] is True
    assert "api_key" not in body


def test_get_never_returns_the_api_key(client, db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="sk-secret", chat_model="gpt-4o", updated_by="admin"
    )

    response = client.get("/admin/llm-settings", auth=AUTH)

    assert "sk-secret" not in response.text
    body = response.json()
    assert body["has_api_key"] is True
    assert body["is_default"] is False
    assert body["chat_model"] == "gpt-4o"


def test_put_rejects_an_unknown_provider(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "anthropic", "chat_model": "claude", "base_url": None, "api_key": "k"},
    )

    assert response.status_code == 400


def test_put_rejects_ollama_without_a_base_url(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "ollama", "chat_model": "llama3.1", "base_url": None, "api_key": None},
    )

    assert response.status_code == 400


def test_put_rejects_an_empty_chat_model(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "  ", "base_url": None, "api_key": "k"},
    )

    assert response.status_code == 400


def test_put_saves_and_audits_without_leaking_the_key(client, db_session):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": "sk-should-not-appear",
        },
    )

    assert response.status_code == 200
    assert llm_settings.resolve(db_session).chat_model == "llama3.1"

    entries = db_session.query(AdminAuditLog).filter_by(action="llm_settings.update").all()
    assert len(entries) == 1
    assert "sk-should-not-appear" not in (entries[0].target or "")


@respx.mock
def test_test_endpoint_reports_success(client):
    respx.post(OLLAMA_CHAT_URL).mock(return_value=httpx.Response(200, json=CHAT_OK))

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": None,
        },
    ).json()

    assert body["ok"] is True
    assert body["model"] == "llama3.1"
    assert isinstance(body["latency_ms"], int)


@respx.mock
def test_test_endpoint_reports_a_provider_failure(client):
    respx.post(OPENAI_CHAT_URL).mock(
        return_value=httpx.Response(401, json={"error": {"message": "Incorrect API key provided"}})
    )

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-bad"},
    ).json()

    assert body["ok"] is False
    assert "Incorrect API key" in body["error"]


@respx.mock
def test_test_endpoint_writes_no_token_usage(client, db_session):
    from app.db.models import TokenUsage

    respx.post(OPENAI_CHAT_URL).mock(return_value=httpx.Response(200, json=CHAT_OK))

    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-good"},
    )

    assert db_session.query(TokenUsage).count() == 0


@respx.mock
def test_test_endpoint_records_no_retry_metric(client):
    from prometheus_client import REGISTRY

    def _total_retries() -> float:
        # Sum every call_type: asserting on one label would pass trivially,
        # because a series that was never touched reads as absent.
        total = 0.0
        for metric in REGISTRY.collect():
            if metric.name == "llm_retries":
                total += sum(sample.value for sample in metric.samples)
        return total

    route = respx.post(OPENAI_CHAT_URL).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    before = _total_retries()

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-good"},
    ).json()

    assert body["ok"] is False
    assert route.called
    # The OpenAI SDK retries 5xx internally; what this asserts is that the
    # endpoint adds no retry_once of its own and dirties no retry metric.
    assert _total_retries() == before


@respx.mock
def test_test_endpoint_uses_the_stored_key_when_none_is_supplied(client, db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="sk-stored", chat_model="gpt-4o-mini", updated_by="admin"
    )

    captured = {}

    def _capture(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=CHAT_OK)

    respx.post(OPENAI_CHAT_URL).mock(side_effect=_capture)

    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": None},
    )

    assert captured["auth"] == "Bearer sk-stored"


@respx.mock
def test_test_endpoint_leaves_the_cached_client_alone(client, db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    before = get_chat_client(db_session)

    respx.post(OLLAMA_CHAT_URL).mock(return_value=httpx.Response(200, json=CHAT_OK))
    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": None,
        },
    )

    assert get_chat_client(db_session) is before


def test_put_invalidates_the_cached_client(client, db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    before = get_chat_client(db_session)

    client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": None,
        },
    )

    assert get_chat_client(db_session) is not before


def test_put_with_a_blank_key_keeps_the_stored_one(client, db_session):
    llm_settings.save(
        db_session, provider="openai", base_url=None, api_key="sk-keep", chat_model="gpt-4o-mini", updated_by="admin"
    )

    client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o", "base_url": None, "api_key": None},
    )

    resolved = llm_settings.resolve(db_session)
    assert resolved.api_key == "sk-keep"
    assert resolved.chat_model == "gpt-4o"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_admin_llm_settings.py -q
```
Expected: FAIL — the routes return 404.

- [ ] **Step 3: Write the router**

Create `backend/app/routers/admin_llm_settings.py`:

```python
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import llm_settings
from app.agent.clients import build_chat_client, invalidate_chat_client
from app.auth import log_admin_action, require_admin
from app.db.base import get_db

router = APIRouter(prefix="/admin/llm-settings")

_TEST_MAX_TOKENS = 5
_ERROR_MAX_CHARS = 200


class SettingsPayload(BaseModel):
    provider: str
    chat_model: str
    base_url: str | None = None
    # None means "keep whatever is stored"; the UI never sends the saved key back.
    api_key: str | None = None


def _validate(payload: SettingsPayload) -> None:
    if payload.provider not in llm_settings.PROVIDERS:
        raise HTTPException(status_code=400, detail=f"provider must be one of {llm_settings.PROVIDERS}")
    if not payload.chat_model.strip():
        raise HTTPException(status_code=400, detail="chat_model must not be empty")
    if payload.provider == "ollama":
        if not (payload.base_url or "").strip():
            raise HTTPException(status_code=400, detail="base_url is required for ollama")
        if not payload.base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="base_url must start with http:// or https://")


def _key_for(payload: SettingsPayload, db: Session) -> str:
    """The key to use right now: the supplied one, else whatever is stored."""
    if payload.api_key:
        return payload.api_key
    return llm_settings.resolve(db).api_key


@router.get("")
def read_settings(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    resolved = llm_settings.resolve(db)
    row = llm_settings.read_row(db)
    return {
        "provider": resolved.provider,
        "base_url": resolved.base_url,
        "chat_model": resolved.chat_model,
        # The key itself is never serialised, in any form.
        "has_api_key": bool(resolved.api_key),
        "is_default": resolved.is_default,
        "updated_at": row.updated_at.isoformat() if row else None,
        "updated_by": row.updated_by if row else None,
    }


@router.post("/test")
def test_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    """Try an unsaved configuration with one cheap call.

    Three deliberate choices: a throwaway client, so a broken configuration
    cannot disturb the one serving customers; no retry_once, so a failure is
    reported immediately and llm_retries_total stays clean; and no
    token_usage row, because this is an administrator's call, not a
    customer's.
    """
    _validate(payload)

    client = build_chat_client(payload.provider, payload.base_url, _key_for(payload, db))
    started = time.monotonic()
    try:
        client.chat.completions.create(
            model=payload.chat_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=_TEST_MAX_TOKENS,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:_ERROR_MAX_CHARS]}

    return {
        "ok": True,
        "model": payload.chat_model,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


@router.put("")
def update_settings(
    payload: SettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    _validate(payload)

    llm_settings.save(
        db,
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        chat_model=payload.chat_model.strip(),
        updated_by=admin_user,
    )
    invalidate_chat_client()

    log_admin_action(
        db,
        action="llm_settings.update",
        # No api_key here, in any form — this record is readable in the UI.
        target=f"{payload.provider} {payload.base_url or ''} {payload.chat_model}".strip(),
        ip=request.client.host if request.client else "",
    )

    return read_settings(db=db, admin_user=admin_user)
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add `admin_llm_settings` to the routers import list and add `app.include_router(admin_llm_settings.router)` alongside the other `include_router` calls.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest tests/test_admin_llm_settings.py -q
```
Expected: PASS, 15 tests.

- [ ] **Step 6: Run the whole suite, lint, and commit**

```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest -q
cd backend && ruff check . && ruff format --check .
git add backend/app/routers/admin_llm_settings.py backend/app/main.py backend/tests/test_admin_llm_settings.py
git commit -m "feat: add the LLM settings admin API"
```

---

### Task 5: Settings page, route, and sidebar link

**Files:**
- Create: `frontend/src/settings/SettingsPage.tsx`
- Create: `frontend/tests/settings/SettingsPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

**Interfaces:**
- Consumes: `GET`, `POST /test`, `PUT` at `/admin/llm-settings` from Task 4; `apiFetch<T>(path, options)` from `src/api/client.ts`.
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/settings/SettingsPage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { SettingsPage } from "../../src/settings/SettingsPage";

const SAVED_SETTINGS = {
  provider: "openai",
  base_url: null,
  chat_model: "gpt-4o-mini",
  has_api_key: true,
  is_default: false,
  updated_at: "2026-09-07T10:00:00Z",
  updated_by: "admin",
};

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
  server.use(http.get(`${API_BASE}/admin/llm-settings`, () => HttpResponse.json(SAVED_SETTINGS)));
});

describe("SettingsPage", () => {
  it("keeps Save disabled until a test succeeds", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() => expect(save).toBeEnabled());
  });

  it("disables Save again when a field changes after a successful test", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(save).toBeEnabled());

    // A configuration must never be saved on the strength of a test of a
    // different configuration.
    await userEvent.type(screen.getByLabelText("Chat model"), "-turbo");

    expect(save).toBeDisabled();
  });

  it("shows the base URL field only for Ollama", async () => {
    render(<SettingsPage />);
    await screen.findByRole("button", { name: "Save" });

    expect(screen.queryByLabelText("Base URL")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Provider"), "ollama");

    expect(screen.getByLabelText("Base URL")).toBeInTheDocument();
  });

  it("reports a failed test and leaves Save disabled", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: false, error: "Incorrect API key provided" })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));

    expect(await screen.findByText(/Incorrect API key provided/)).toBeInTheDocument();
    expect(save).toBeDisabled();
  });

  it("announces that the environment default is in use", async () => {
    server.use(
      http.get(`${API_BASE}/admin/llm-settings`, () =>
        HttpResponse.json({ ...SAVED_SETTINGS, is_default: true, updated_at: null, updated_by: null })
      )
    );
    render(<SettingsPage />);

    expect(await screen.findByText(/default configuration from environment variables/i)).toBeInTheDocument();
  });

  it("never renders the API key field with a value", async () => {
    render(<SettingsPage />);

    const field = await screen.findByLabelText("API key");
    expect(field).toHaveValue("");
    expect(screen.getByText(/leave blank to keep/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run tests/settings/SettingsPage.test.tsx`
Expected: FAIL — cannot resolve `../../src/settings/SettingsPage`.

- [ ] **Step 3: Write the page**

Create `frontend/src/settings/SettingsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface LLMSettings {
  provider: string;
  base_url: string | null;
  chat_model: string;
  has_api_key: boolean;
  is_default: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

interface TestResult {
  ok: boolean;
  model?: string;
  latency_ms?: number;
  error?: string;
}

interface FormState {
  provider: string;
  baseUrl: string;
  apiKey: string;
  chatModel: string;
}

const fieldClass =
  "rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none";

const OLLAMA_PLACEHOLDER = "http://host.docker.internal:11434/v1";

export function SettingsPage() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [form, setForm] = useState<FormState>({ provider: "openai", baseUrl: "", apiKey: "", chatModel: "" });
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function load(): Promise<void> {
    try {
      const data = await apiFetch<LLMSettings>("/admin/llm-settings");
      setSettings(data);
      setForm({
        provider: data.provider,
        baseUrl: data.base_url ?? "",
        apiKey: "",
        chatModel: data.chat_model,
      });
      setError(null);
    } catch {
      setError("Failed to load settings");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Any edit invalidates a previous test result: otherwise a configuration
  // could be saved on the strength of a test of a different configuration.
  function update(patch: Partial<FormState>): void {
    setTestResult(null);
    setSaved(false);
    setForm((current) => ({ ...current, ...patch }));
  }

  function payload() {
    return {
      provider: form.provider,
      chat_model: form.chatModel,
      base_url: form.provider === "ollama" ? form.baseUrl : null,
      api_key: form.apiKey === "" ? null : form.apiKey,
    };
  }

  async function runTest(): Promise<void> {
    setTesting(true);
    try {
      const result = await apiFetch<TestResult>("/admin/llm-settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      setTestResult(result);
      setError(null);
    } catch {
      setError("Failed to reach the server");
    } finally {
      setTesting(false);
    }
  }

  async function save(): Promise<void> {
    setSaving(true);
    try {
      await apiFetch<LLMSettings>("/admin/llm-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      setTestResult(null);
      setSaved(true);
      // Re-read so the page shows what the server holds, not what was typed.
      await load();
    } catch {
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  const canSave = testResult?.ok === true && !saving;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Choose the LLM provider used for the bot&apos;s conversation.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {settings?.is_default && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Using the default configuration from environment variables. Saving here overrides it.
        </p>
      )}

      {saved && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Settings saved.</p>
      )}

      <div className="flex max-w-xl flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-card">
        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Provider
          <select
            aria-label="Provider"
            value={form.provider}
            onChange={(e) => update({ provider: e.target.value })}
            className={fieldClass}
          >
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama</option>
          </select>
        </label>

        {form.provider === "ollama" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
            Base URL
            <input
              aria-label="Base URL"
              value={form.baseUrl}
              placeholder={OLLAMA_PLACEHOLDER}
              onChange={(e) => update({ baseUrl: e.target.value })}
              className={fieldClass}
            />
          </label>
        )}

        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          API key
          <input
            aria-label="API key"
            type="password"
            value={form.apiKey}
            onChange={(e) => update({ apiKey: e.target.value })}
            className={fieldClass}
          />
          {settings?.has_api_key && (
            <span className="text-xs text-muted-foreground">Saved — leave blank to keep the current key.</span>
          )}
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Chat model
          <input
            aria-label="Chat model"
            value={form.chatModel}
            onChange={(e) => update({ chatModel: e.target.value })}
            className={fieldClass}
          />
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={runTest}
            disabled={testing}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Test connection
          </button>
          {testResult?.ok === true && (
            <span className="text-sm text-emerald-700">
              OK — {testResult.model}, {testResult.latency_ms}ms
            </span>
          )}
          {testResult?.ok === false && <span className="text-sm text-red-700">{testResult.error}</span>}
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={save}
            disabled={!canSave}
            className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            Save
          </button>
          {form.provider === "ollama" && (
            <span className="text-xs text-muted-foreground">
              Ollama has no per-token cost, so the cost chart will read zero.
            </span>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Embeddings always use OpenAI (text-embedding-3-small). Changing the provider here does not affect the
        knowledge base.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Add the route and the sidebar link**

In `frontend/src/App.tsx`, add the import `import { SettingsPage } from "./settings/SettingsPage";` and, as the **last** route inside `/panel`:

```tsx
            <Route path="settings" element={<SettingsPage />} />
```

In `frontend/src/layout/AppShell.tsx`, add as the **last** entry in `<nav>`, after Channels:

```tsx
          <NavLink to="/panel/settings" className={linkClass}>
            Settings
          </NavLink>
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/settings/SettingsPage.test.tsx`
Expected: PASS, 6 tests.

- [ ] **Step 6: Typecheck, build, and run the whole frontend suite**

```bash
cd frontend && npm run build
cd frontend && npm run test
```
Expected: the build succeeds. The suite shows exactly the two pre-existing failures named in Global Constraints (`WelcomePage`, `App`) and nothing else.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/settings/SettingsPage.tsx frontend/tests/settings/SettingsPage.test.tsx frontend/src/App.tsx frontend/src/layout/AppShell.tsx
git commit -m "feat: add a Settings page for choosing the LLM provider"
```

---

### Task 6: Documentation

**Files:**
- Modify: `README.md`
- Modify: `infra/README.md`

**Interfaces:**
- Consumes: everything above. Produces nothing consumed by code.

- [ ] **Step 1: Update the root README**

In the Admin API table, add:

```markdown
| GET/PUT | `/admin/llm-settings` | Read / update the active LLM provider and chat model |
| POST | `/admin/llm-settings/test` | Test a provider configuration before saving |
```

In the key-features list, add a bullet:

```markdown
- **Switchable LLM provider**: a Settings page selects OpenAI or any OpenAI-compatible endpoint (Ollama) and the chat model, stored encrypted in the database and effective without a restart (`app/llm_settings.py`, `app/routers/admin_llm_settings.py`). Embeddings stay on OpenAI's `text-embedding-3-small`, because the Chroma index depends on it.
```

In the Project layout block, add under `backend/app/`:

```
    llm_settings.py        # active chat provider/model: DB-backed, env fallback, encrypted key
    routers/admin_llm_settings.py  # GET/PUT /admin/llm-settings, POST /admin/llm-settings/test
```

- [ ] **Step 2: Update the infra README**

Add a section to `infra/README.md`, after "Routine operations":

```markdown
## Using Ollama

The LLM provider is chosen in the admin panel under Settings, not in Terraform.

Two things to know when pointing it at Ollama:

- **Do not run Ollama on this instance.** A `t3.small` has 2 GB of RAM, which the
  application stack and the monitoring stack already share. Run Ollama on a
  separate host and give its URL in the Settings page.
- **Port 11434 is not open.** The security group opens only 80, 3000, and 22. If
  the Ollama host is reachable over the public internet it needs no change here;
  if you place it inside the VPC, add an egress path deliberately rather than
  widening ingress.

When the backend runs in Docker on a developer machine, `http://localhost:11434`
points at the container itself. Use `http://host.docker.internal:11434/v1`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md infra/README.md
git commit -m "docs: document the LLM provider settings"
```

---

## Verification checklist

After all tasks are done:

- [ ] `cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY=***REMOVED*** pytest -q` — the whole suite passes
- [ ] `cd backend && ruff check . && ruff format --check .` — clean
- [ ] `cd backend && ! grep -rn "get_openai_client" app/ tests/` — no references to the removed function survive
- [ ] `cd backend && grep -rn "REWRITE_MODEL\|RERANK_MODEL\|CHUNK_MODEL" app/` — no matches; those constants are gone
- [ ] `cd frontend && npm run build` — succeeds
- [ ] `cd frontend && npm run test` — only the two pre-existing failures (`WelcomePage`, `App`)
- [ ] `alembic upgrade head` then `alembic downgrade 0003` both succeed on a scratch database
- [ ] No endpoint response, audit log entry, or rendered page contains an API key: `grep -rn "api_key" backend/app/routers/admin_llm_settings.py` shows it only in the request model, the validation helper, and the call to `llm_settings.save`
- [ ] Manual: point at the real Ollama server, exchange a message over Telegram, and confirm in Grafana that `llm_tokens_total` carries the new model label and `agent_node_duration_seconds` still records
