# Matcha Bot Backend Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend service — Telegram webhook + LangGraph
RAG agent + Postgres persistence + admin API (docs, users, logs) — as a
standalone, independently testable service. Frontend SPA and infra/CI-CD
are separate plans that consume this service's API.

**Architecture:** Single FastAPI app (`backend/app/`). SQLAlchemy 2.0 sync
ORM against Postgres (SQLite in-memory for tests via dependency override).
A LangGraph `StateGraph` with four nodes (`fetch_history`, `retrieve`,
`generate`, `extract_favourite`) implements the agent. Telegram webhook and
`/admin/*` routes are thin FastAPI routers that call into the agent graph,
DB models, and Qdrant/OpenAI clients. HTTP Basic Auth (single shared
credential) guards all `/admin/*` routes; every admin call writes a row to
`admin_audit_log`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Postgres
(psycopg2), LangGraph, OpenAI Python SDK, Qdrant client, httpx (Telegram
API calls), pytest + FastAPI TestClient, SQLite in-memory for test DB.

**Spec:** docs/superpowers/specs/2026-09-02-matcha-tea-bot-design.md

## Global Constraints

- LLM calls use the OpenAI API, not AWS Bedrock.
- Vector store is Qdrant Cloud (managed) via `qdrant-client`.
- `/admin/*` routes use a single shared HTTP Basic Auth credential from env
  vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`) — no multi-admin accounts.
- Every `/admin/*` call writes one row to `admin_audit_log` (action,
  target, ip, timestamp).
- Telegram webhook always returns HTTP 200 immediately; internal failures
  are logged and surfaced to the user as a fallback reply, never a 5xx.
- If a user's `blocked` flag is set, the webhook ACKs the update but does
  not invoke the agent graph or send a reply.
- `extract_favourite` runs after the reply is sent (fire-and-forget
  in-process asyncio task) — it must never delay the reply.
- No managed cloud function/queue (Lambda, SQS, etc.) for any task —
  everything in this plan runs as plain Python inside the `backend`
  container; this plan does not touch CI/CD (that's the infra plan).
- Recipes are just documents — no separate recipe type, table, or route.
  They go through the same `/admin/docs` upload path as any other
  brewing-knowledge doc.

---

## File Structure

```
backend/
  pyproject.toml
  alembic.ini
  app/
    __init__.py
    main.py                  # FastAPI app, mounts routers
    config.py                 # Settings from env vars
    db/
      __init__.py
      base.py                 # engine, SessionLocal, Base, get_db dependency
      models.py                # User, Message, Favourite, Document, AdminAuditLog
    auth.py                   # Basic Auth dependency + audit log writer
    telegram_client.py        # send_message() wrapper over Telegram Bot API
    agent/
      __init__.py
      state.py                 # Pydantic AgentState
      nodes.py                  # fetch_history, retrieve, generate, extract_favourite
      graph.py                   # build_graph() wiring the 4 nodes
      clients.py                 # OpenAI client factory, Qdrant client factory
    routers/
      __init__.py
      health.py                  # GET /health
      webhook.py                  # POST /webhook/telegram
      admin_docs.py                # /admin/docs
      admin_users.py                # /admin/users
      admin_logs.py                  # /admin/logs/access, /admin/logs/audit
    ingestion.py                     # chunk_text(), embed_and_upsert()
  migrations/
    env.py
    versions/
      0001_initial.py
  tests/
    conftest.py
    test_health.py
    test_auth.py
    test_agent_nodes.py
    test_agent_graph.py
    test_webhook.py
    test_admin_docs.py
    test_admin_users.py
    test_admin_logs.py
```

**Interfaces produced by this plan** (consumed by the frontend and infra
plans):

- `GET /health` → `{"status": "ok"}`, HTTP 200
- `POST /webhook/telegram` → always HTTP 200, empty body
- `GET/POST/DELETE /admin/docs` — Basic Auth
- `GET /admin/users`, `POST /admin/users/{id}/block`,
  `POST /admin/users/{id}/unblock` — Basic Auth
- `GET /admin/logs/access`, `GET /admin/logs/audit` — Basic Auth,
  query params `?limit=&offset=`
- `backend/Dockerfile` is NOT part of this plan — the infra plan adds it,
  consuming `backend/pyproject.toml` as the dependency source of truth.

---

### Task 1: Project scaffold + health endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings, fields:
  `openai_api_key: str`, `qdrant_url: str`, `qdrant_api_key: str`,
  `telegram_bot_token: str`, `database_url: str`, `admin_username: str`,
  `admin_password: str`), `app.config.get_settings() -> Settings`
- Produces: `app.main.app` (FastAPI instance)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "matcha-bot-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg2-binary>=2.9",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "openai>=1.50",
    "qdrant-client>=1.11",
    "langgraph>=0.2",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-mock>=3.14",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
```

- [ ] **Step 2: Write `app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    telegram_bot_token: str = ""
    database_url: str = "sqlite:///./local.db"
    admin_username: str = "admin"
    admin_password: str = "admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Write `app/routers/__init__.py`** (empty file)

```python
```

- [ ] **Step 4: Write `app/routers/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Write `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
```

- [ ] **Step 6: Write `app/__init__.py`** (empty file)

```python
```

- [ ] **Step 7: Write failing test `tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Write `tests/conftest.py`** (empty for now, will grow in Task 2)

```python
```

- [ ] **Step 9: Install deps and run test**

Run (from `backend/`):
```bash
pip install -e ".[dev]"
pytest tests/test_health.py -v
```
Expected: PASS (this task has no red-green cycle since the endpoint is
trivial — write it correct the first time, then verify with the test).

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

### Task 2: DB models + Alembic migration

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/versions/0001_initial.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `app.db.base.Base`, `app.db.base.engine`,
  `app.db.base.SessionLocal`, `app.db.base.get_db()` (FastAPI dependency,
  yields a `Session`)
- Produces models: `User(id, telegram_user_id, first_seen, blocked)`,
  `Message(id, user_id, role, content, created_at)`,
  `Favourite(id, user_id, drink_name, confidence, source, created_at)`,
  `Document(id, filename, chunk_count, uploaded_at)`,
  `AdminAuditLog(id, action, target, ip, created_at)`

- [ ] **Step 1: Write `app/db/base.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Write `app/db/models.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    favourites: Mapped[list["Favourite"]] = relationship(back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="messages")


class Favourite(Base):
    __tablename__ = "favourites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drink_name: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String, default="inferred")
    source: Mapped[str] = mapped_column(String, default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="favourites")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    chunk_count: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String, default="")
    ip: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
```

- [ ] **Step 3: Write `app/db/__init__.py`** (empty file)

```python
```

- [ ] **Step 4: Write `tests/conftest.py`** (SQLite in-memory DB fixture, overrides `get_db`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, get_db
from app.main import app

TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Write failing test `tests/test_models.py`**

```python
from app.db.models import User, Message, Favourite, Document, AdminAuditLog


def test_create_user_with_related_rows(db_session):
    user = User(telegram_user_id="123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user.id, drink_name="genmaicha"))
    db_session.add(Document(filename="brewing.pdf", chunk_count=5))
    db_session.add(AdminAuditLog(action="login"))
    db_session.commit()

    assert db_session.query(Message).count() == 1
    assert db_session.query(Favourite).count() == 1
    assert db_session.query(Document).count() == 1
    assert db_session.query(AdminAuditLog).count() == 1
    assert user.blocked is False
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest backend/tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.models'`
(models file doesn't exist yet if you're doing strict TDD; since Steps 1-2
already wrote it, instead run this as the verification step and expect
PASS. If you want true red-green, write Step 5's test before Steps 1-2.)

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest backend/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 8: Set up Alembic** — `backend/alembic.ini`

```ini
[alembic]
script_location = migrations
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 9: Write `migrations/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers models on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 10: Write `migrations/versions/0001_initial.py`**

```python
"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_user_id", sa.String, unique=True, index=True, nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "favourites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("drink_name", sa.String, nullable=False),
        sa.Column("confidence", sa.String, nullable=False, server_default="inferred"),
        sa.Column("source", sa.String, nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("target", sa.String, nullable=False, server_default=""),
        sa.Column("ip", sa.String, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("documents")
    op.drop_table("favourites")
    op.drop_table("messages")
    op.drop_table("users")
```

- [ ] **Step 11: Commit**

```bash
git add backend/app/db backend/alembic.ini backend/migrations backend/tests
git commit -m "feat(backend): add DB models and initial Alembic migration"
```

---

### Task 3: Basic Auth dependency + audit log writer

**Files:**
- Create: `backend/app/auth.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1), `app.db.base.get_db`,
  `app.db.models.AdminAuditLog` (Task 2)
- Produces: `app.auth.require_admin(credentials: HTTPBasicCredentials = Depends(...)) -> str`
  (FastAPI dependency, returns the username; raises 401 on bad creds),
  `app.auth.log_admin_action(db: Session, action: str, target: str = "", ip: str = "") -> None`

- [ ] **Step 1: Write failing test `tests/test_auth.py`**

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_admin


def test_require_admin_rejects_bad_credentials(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    config.get_settings.cache_clear()

    probe = FastAPI()

    @probe.get("/probe")
    def probe_route(user: str = Depends(require_admin)):
        return {"user": user}

    client = TestClient(probe)

    ok = client.get("/probe", auth=("admin", "secret"))
    assert ok.status_code == 200
    assert ok.json() == {"user": "admin"}

    bad = client.get("/probe", auth=("admin", "wrong"))
    assert bad.status_code == 401

    config.get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Write `app/auth.py`**

```python
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import get_db
from app.db.models import AdminAuditLog

security = HTTPBasic()


def require_admin(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    settings = get_settings()
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def log_admin_action(db: Session, action: str, target: str = "", ip: str = "") -> None:
    db.add(
        AdminAuditLog(
            action=action,
            target=target,
            ip=ip,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add Basic Auth dependency and audit log writer"
```

---

### Task 4: Telegram client wrapper

**Files:**
- Create: `backend/app/telegram_client.py`
- Test: `backend/tests/test_telegram_client.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `app.telegram_client.send_message(chat_id: str, text: str) -> None`
  (async; raises `httpx.HTTPStatusError` on non-2xx after logging)

- [ ] **Step 1: Write failing test `tests/test_telegram_client.py`**

```python
import httpx
import pytest

from app.telegram_client import send_message


@pytest.mark.asyncio
async def test_send_message_posts_to_telegram_api(monkeypatch, respx_mock=None):
    import respx

    with respx.mock:
        route = respx.post(
            "https://api.telegram.org/botTEST_TOKEN/sendMessage"
        ).mock(return_value=httpx.Response(200, json={"ok": True}))

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST_TOKEN")
        from app import config

        config.get_settings.cache_clear()

        await send_message(chat_id="42", text="hello")

        assert route.called
        sent = route.calls.last.request
        assert b'"chat_id": "42"' in sent.content or b'"chat_id":"42"' in sent.content

        config.get_settings.cache_clear()
```

- [ ] **Step 2: Add test deps to `pyproject.toml`** — extend the `dev` list from Task 1

```toml
dev = [
    "pytest>=8.3",
    "pytest-mock>=3.14",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]
```

Run: `pip install -e ".[dev]"`

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_telegram_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.telegram_client'`

- [ ] **Step 4: Write `app/telegram_client.py`**

```python
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_message(chat_id: str, text: str) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        logger.error("Telegram sendMessage failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
```

- [ ] **Step 5: Add `[tool.pytest.ini_options]` for asyncio mode** — append to `pyproject.toml`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest backend/tests/test_telegram_client.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/telegram_client.py backend/tests/test_telegram_client.py backend/pyproject.toml
git commit -m "feat(backend): add Telegram sendMessage client wrapper"
```

---

### Task 5: Agent state + fetch_history node

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/state.py`
- Create: `backend/app/agent/nodes.py`
- Test: `backend/tests/test_agent_nodes.py`

**Interfaces:**
- Consumes: `app.db.models.User`, `app.db.models.Message`,
  `app.db.models.Favourite` (Task 2)
- Produces: `app.agent.state.AgentState` (pydantic `BaseModel`: `user_id: int`,
  `chat_id: str`, `incoming_text: str`, `history: list[dict]`,
  `favourites: list[str]`, `retrieved_chunks: list[str]`, `reply: str = ""`)
- Produces: `app.agent.nodes.fetch_history(state: AgentState, db: Session) -> AgentState`

- [ ] **Step 1: Write `app/agent/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Write `app/agent/state.py`**

```python
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    user_id: int
    chat_id: str
    incoming_text: str
    history: list[dict] = Field(default_factory=list)
    favourites: list[str] = Field(default_factory=list)
    retrieved_chunks: list[str] = Field(default_factory=list)
    reply: str = ""
```

- [ ] **Step 3: Write failing test `tests/test_agent_nodes.py`**

```python
from app.agent.nodes import fetch_history
from app.agent.state import AgentState
from app.db.models import User, Message, Favourite


def test_fetch_history_loads_recent_messages_and_favourites(db_session):
    user = User(telegram_user_id="99")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Message(user_id=user.id, role="assistant", content="hello!"))
    db_session.add(Favourite(user_id=user.id, drink_name="hojicha"))
    db_session.commit()

    state = AgentState(user_id=user.id, chat_id="99", incoming_text="what do you recommend?")
    result = fetch_history(state, db_session)

    assert len(result.history) == 2
    assert result.history[0]["content"] == "hi"
    assert result.favourites == ["hojicha"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.agent.nodes'`

- [ ] **Step 5: Write `app/agent/nodes.py`** (fetch_history only for this task; other
  nodes added in Tasks 6-8)

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.state import AgentState
from app.db.models import Favourite, Message


def fetch_history(state: AgentState, db: Session, limit: int = 10) -> AgentState:
    rows = (
        db.execute(
            select(Message)
            .where(Message.user_id == state.user_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    state.history = [{"role": m.role, "content": m.content} for m in rows]

    favourite_rows = (
        db.execute(select(Favourite).where(Favourite.user_id == state.user_id))
        .scalars()
        .all()
    )
    state.favourites = [f.drink_name for f in favourite_rows]
    return state
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/agent backend/tests/test_agent_nodes.py
git commit -m "feat(backend): add agent state and fetch_history node"
```

---

### Task 6: retrieve node (Qdrant)

**Files:**
- Create: `backend/app/agent/clients.py`
- Modify: `backend/app/agent/nodes.py` (add `retrieve`)
- Modify: `backend/app/config.py` — no change needed, `qdrant_url`/`qdrant_api_key` already present
- Test: `backend/tests/test_agent_nodes.py` (add retrieve test)

**Interfaces:**
- Consumes: `app.config.get_settings()`, `app.agent.state.AgentState`
- Produces: `app.agent.clients.get_qdrant_client() -> QdrantClient`,
  `app.agent.clients.get_openai_client() -> OpenAI`
- Produces: `app.agent.nodes.retrieve(state: AgentState, qdrant_client, openai_client, collection: str = "matcha_knowledge") -> AgentState`

- [ ] **Step 1: Write `app/agent/clients.py`**

```python
from functools import lru_cache

from openai import OpenAI
from qdrant_client import QdrantClient

from app.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)
```

- [ ] **Step 2: Write failing test — append to `tests/test_agent_nodes.py`**

```python
from unittest.mock import MagicMock

from app.agent.nodes import retrieve


def test_retrieve_queries_qdrant_and_fills_chunks():
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_point = MagicMock()
    fake_point.payload = {"text": "Whisk matcha with a bamboo chasen."}
    fake_qdrant = MagicMock()
    fake_qdrant.search.return_value = [fake_point]

    result = retrieve(state, qdrant_client=fake_qdrant, openai_client=fake_openai)

    fake_openai.embeddings.create.assert_called_once()
    fake_qdrant.search.assert_called_once()
    assert result.retrieved_chunks == ["Whisk matcha with a bamboo chasen."]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: FAIL with `ImportError: cannot import name 'retrieve'`

- [ ] **Step 4: Add `retrieve` to `app/agent/nodes.py`**

```python
def retrieve(
    state: AgentState,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
    top_k: int = 5,
) -> AgentState:
    embedding = (
        openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=state.incoming_text,
        )
        .data[0]
        .embedding
    )
    hits = qdrant_client.search(collection_name=collection, query_vector=embedding, limit=top_k)
    state.retrieved_chunks = [hit.payload.get("text", "") for hit in hits]
    return state
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/clients.py backend/app/agent/nodes.py backend/tests/test_agent_nodes.py
git commit -m "feat(backend): add retrieve node with Qdrant/OpenAI clients"
```

---

### Task 7: generate node (OpenAI)

**Files:**
- Modify: `backend/app/agent/nodes.py` (add `generate`)
- Test: `backend/tests/test_agent_nodes.py` (add generate test)

**Interfaces:**
- Consumes: `app.agent.state.AgentState`, an OpenAI client (Task 6)
- Produces: `app.agent.nodes.generate(state: AgentState, openai_client) -> AgentState`
  (sets `state.reply`)

- [ ] **Step 1: Write failing test — append to `tests/test_agent_nodes.py`**

```python
from app.agent.nodes import generate


def test_generate_calls_openai_with_context_and_sets_reply():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="what matcha do you recommend?",
        history=[{"role": "user", "content": "hi"}],
        favourites=["hojicha"],
        retrieved_chunks=["Ceremonial grade matcha is best whisked, not shaken."],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Try our ceremonial grade matcha!"))
    ]

    result = generate(state, openai_client=fake_openai)

    fake_openai.chat.completions.create.assert_called_once()
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    system_message = call_kwargs["messages"][0]["content"]
    assert "hojicha" in system_message
    assert "Ceremonial grade matcha is best whisked, not shaken." in system_message
    assert result.reply == "Try our ceremonial grade matcha!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate'`

- [ ] **Step 3: Add `generate` to `app/agent/nodes.py`**

```python
def _build_system_prompt(state: AgentState) -> str:
    favourites = ", ".join(state.favourites) or "none known yet"
    context = "\n".join(f"- {chunk}" for chunk in state.retrieved_chunks) or "(no matching knowledge found)"
    return (
        "You are a premium matcha and tea ceremony consultant. "
        f"The user's known favourite drinks: {favourites}. "
        f"Relevant knowledge:\n{context}\n"
        "Answer helpfully and recommend products/brewing methods when relevant."
    )


def generate(state: AgentState, openai_client, model: str = "gpt-4o-mini") -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    messages.extend(state.history)
    messages.append({"role": "user", "content": state.incoming_text})

    response = openai_client.chat.completions.create(model=model, messages=messages)
    state.reply = response.choices[0].message.content
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/nodes.py backend/tests/test_agent_nodes.py
git commit -m "feat(backend): add generate node calling OpenAI chat completions"
```

---

### Task 8: extract_favourite node

**Files:**
- Modify: `backend/app/agent/nodes.py` (add `extract_favourite`)
- Test: `backend/tests/test_agent_nodes.py` (add extract_favourite test)

**Interfaces:**
- Consumes: `app.agent.state.AgentState`, an OpenAI client, `Session`,
  `app.db.models.Favourite`
- Produces: `app.agent.nodes.extract_favourite(state: AgentState, db: Session, openai_client) -> None`
  (writes to DB directly, does not mutate/return state — this node runs
  fire-and-forget after the reply is sent, per Global Constraints)

- [ ] **Step 1: Write failing test — append to `tests/test_agent_nodes.py`**

```python
from app.agent.nodes import extract_favourite
from app.db.models import Favourite


def test_extract_favourite_upserts_when_preference_detected(db_session):
    user = User(telegram_user_id="7")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="7", incoming_text="I really love sencha the most")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": "sencha"}'))
    ]

    extract_favourite(state, db=db_session, openai_client=fake_openai)

    rows = db_session.query(Favourite).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].drink_name == "sencha"


def test_extract_favourite_noop_when_no_preference(db_session):
    user = User(telegram_user_id="8")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="8", incoming_text="what time do you close?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": null}'))
    ]

    extract_favourite(state, db=db_session, openai_client=fake_openai)

    assert db_session.query(Favourite).filter_by(user_id=user.id).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: FAIL with `ImportError: cannot import name 'extract_favourite'`

- [ ] **Step 3: Add `extract_favourite` to `app/agent/nodes.py`**

```python
import json

from app.db.models import Favourite


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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_nodes.py -v`
Expected: PASS (both new tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/nodes.py backend/tests/test_agent_nodes.py
git commit -m "feat(backend): add extract_favourite node"
```

---

### Task 9: LangGraph wiring

**Files:**
- Create: `backend/app/agent/graph.py`
- Test: `backend/tests/test_agent_graph.py`

**Interfaces:**
- Consumes: `app.agent.nodes.fetch_history`, `retrieve`, `generate`
  (Tasks 5-7). `extract_favourite` is deliberately NOT wired into the
  graph — it's invoked separately as a fire-and-forget task after the
  reply is sent (Task 10), per Global Constraints.
- Produces: `app.agent.graph.run_agent(state: AgentState, db: Session, qdrant_client, openai_client) -> AgentState`

- [ ] **Step 1: Write failing test `tests/test_agent_graph.py`**

```python
from unittest.mock import MagicMock

from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.db.models import User


def test_run_agent_produces_a_reply(db_session):
    user = User(telegram_user_id="55")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="55", incoming_text="recommend a matcha")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Try ceremonial grade!"))
    ]

    fake_qdrant = MagicMock()
    fake_qdrant.search.return_value = []

    result = run_agent(state, db=db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    assert result.reply == "Try ceremonial grade!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.agent.graph'`

- [ ] **Step 3: Write `app/agent/graph.py`**

LangGraph's `StateGraph` needs a `TypedDict`/mapping-like state; since
`AgentState` is a pydantic model, this wires the three nodes as a plain
sequential pipeline (LangGraph's `StateGraph` is overkill for a 3-node
linear pipeline with no branching — Global Constraints call for
LangGraph, so it's used, but kept to what the graph actually needs).

```python
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import fetch_history, generate, retrieve
from app.agent.state import AgentState


def _fetch_history_step(state: AgentState, db: Session) -> AgentState:
    return fetch_history(state, db)


def build_graph(db: Session, qdrant_client, openai_client):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", lambda s: fetch_history(s, db))
    graph.add_node("retrieve", lambda s: retrieve(s, qdrant_client, openai_client))
    graph.add_node("generate", lambda s: generate(s, openai_client))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(state: AgentState, db: Session, qdrant_client, openai_client) -> AgentState:
    compiled = build_graph(db, qdrant_client, openai_client)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/graph.py backend/tests/test_agent_graph.py
git commit -m "feat(backend): wire fetch_history/retrieve/generate into LangGraph"
```

---

### Task 10: Telegram webhook endpoint

**Files:**
- Create: `backend/app/routers/webhook.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_webhook.py`

**Interfaces:**
- Consumes: `app.agent.graph.run_agent`, `app.agent.nodes.extract_favourite`,
  `app.telegram_client.send_message`, `app.agent.clients.get_qdrant_client`,
  `app.agent.clients.get_openai_client`, `app.db.base.get_db`,
  `app.db.models.User`, `Message`
- Produces: `POST /webhook/telegram` — always HTTP 200

- [ ] **Step 1: Write failing test `tests/test_webhook.py`**

```python
from unittest.mock import AsyncMock, patch

from app.db.models import User


def test_webhook_creates_user_stores_message_and_replies(client, db_session):
    payload = {
        "message": {
            "chat": {"id": 111},
            "from": {"id": 111},
            "text": "hi there",
        }
    }

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch("app.routers.webhook.extract_favourite"):
        from app.agent.state import AgentState

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_send.assert_awaited_once()
    user = db_session.query(User).filter_by(telegram_user_id="111").one()
    assert user is not None


def test_webhook_skips_blocked_user(client, db_session):
    from app.db.models import User as UserModel

    blocked = UserModel(telegram_user_id="222", blocked=True)
    db_session.add(blocked)
    db_session.commit()

    payload = {"message": {"chat": {"id": 222}, "from": {"id": 222}, "text": "hello"}}

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send:
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_run_agent.assert_not_called()
    mock_send.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_webhook.py -v`
Expected: FAIL with `404 Not Found` (route doesn't exist) or import error

- [ ] **Step 3: Write `app/routers/webhook.py`**

```python
import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agent.clients import get_openai_client, get_qdrant_client
from app.agent.graph import run_agent
from app.agent.nodes import extract_favourite
from app.agent.state import AgentState
from app.db.base import get_db
from app.db.models import Message, User
from app.telegram_client import send_message

logger = logging.getLogger(__name__)
router = APIRouter()

FALLBACK_REPLY = "Sorry, having trouble right now — please try again in a bit."


def _get_or_create_user(db: Session, telegram_user_id: str) -> User:
    user = db.query(User).filter_by(telegram_user_id=telegram_user_id).one_or_none()
    if user is None:
        user = User(telegram_user_id=telegram_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    message = payload.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    if not chat_id or not telegram_user_id or not text:
        return {}

    user = _get_or_create_user(db, telegram_user_id)

    if user.blocked:
        return {}

    db.add(Message(user_id=user.id, role="user", content=text))
    db.commit()

    state = AgentState(user_id=user.id, chat_id=chat_id, incoming_text=text)

    try:
        result = run_agent(
            state,
            db=db,
            qdrant_client=get_qdrant_client(),
            openai_client=get_openai_client(),
        )
        reply = result.reply or FALLBACK_REPLY
    except Exception:
        logger.exception("Agent run failed for user_id=%s", user.id)
        reply = FALLBACK_REPLY

    db.add(Message(user_id=user.id, role="assistant", content=reply))
    db.commit()

    await send_message(chat_id=chat_id, text=reply)

    asyncio.create_task(_extract_favourite_background(state, user.id))

    return {}


async def _extract_favourite_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        extract_favourite(state, db=db, openai_client=get_openai_client())
    except Exception:
        logger.exception("extract_favourite failed for user_id=%s", user_id)
    finally:
        db.close()
```

- [ ] **Step 4: Mount router in `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_webhook.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/webhook.py backend/app/main.py backend/tests/test_webhook.py
git commit -m "feat(backend): add Telegram webhook endpoint with blocked-user skip"
```

---

### Task 11: Admin docs endpoints (upload/list/delete + ingestion)

**Files:**
- Create: `backend/app/ingestion.py`
- Create: `backend/app/routers/admin_docs.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_admin_docs.py`

**Interfaces:**
- Consumes: `app.auth.require_admin`, `app.auth.log_admin_action`,
  `app.agent.clients.get_qdrant_client`, `get_openai_client`,
  `app.db.models.Document`
- Produces: `app.ingestion.chunk_text(text: str, chunk_size: int = 500) -> list[str]`,
  `app.ingestion.embed_and_upsert(chunks: list[str], filename: str, qdrant_client, openai_client, collection: str = "matcha_knowledge") -> None`
- Produces: `POST /admin/docs`, `GET /admin/docs`, `DELETE /admin/docs/{id}`

- [ ] **Step 1: Write `app/ingestion.py`**

```python
import uuid


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks or [text]


def embed_and_upsert(
    chunks: list[str],
    filename: str,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
) -> None:
    from qdrant_client.models import PointStruct

    points = []
    for chunk in chunks:
        embedding = (
            openai_client.embeddings.create(model="text-embedding-3-small", input=chunk)
            .data[0]
            .embedding
        )
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={"text": chunk, "source": filename},
            )
        )
    qdrant_client.upsert(collection_name=collection, points=points)
```

- [ ] **Step 2: Write failing test `tests/test_admin_docs.py`**

```python
from io import BytesIO
from unittest.mock import MagicMock, patch

from app.db.models import Document


def test_upload_doc_requires_auth(client):
    response = client.post("/admin/docs", files={"file": ("brew.txt", BytesIO(b"steep 80C"))})
    assert response.status_code == 401


def test_upload_doc_chunks_embeds_and_records_metadata(client, db_session):
    fake_qdrant = MagicMock()
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]

    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant), patch(
        "app.routers.admin_docs.get_openai_client", return_value=fake_openai
    ):
        response = client.post(
            "/admin/docs",
            files={"file": ("sencha_recipe.txt", BytesIO(b"Steep sencha at 70C for 60 seconds."))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sencha_recipe.txt"
    assert db_session.query(Document).count() == 1


def test_list_docs(client, db_session):
    db_session.add(Document(filename="a.txt", chunk_count=1))
    db_session.commit()
    response = client.get("/admin/docs", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_delete_doc(client, db_session):
    doc = Document(filename="a.txt", chunk_count=1)
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    fake_qdrant = MagicMock()
    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant):
        response = client.delete(f"/admin/docs/{doc.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Document).count() == 0
    fake_qdrant.delete.assert_called_once()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_admin_docs.py -v`
Expected: FAIL with `404 Not Found` / import error

- [ ] **Step 4: Write `app/routers/admin_docs.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.agent.clients import get_openai_client, get_qdrant_client
from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Document
from app.ingestion import chunk_text, embed_and_upsert

router = APIRouter(prefix="/admin/docs")


@router.post("", status_code=201)
async def upload_doc(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    chunks = chunk_text(text)

    embed_and_upsert(
        chunks=chunks,
        filename=file.filename,
        qdrant_client=get_qdrant_client(),
        openai_client=get_openai_client(),
    )

    doc = Document(filename=file.filename, chunk_count=len(chunks))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_admin_action(db, action="upload_doc", target=file.filename, ip=request.client.host if request.client else "")

    return {"id": doc.id, "filename": doc.filename, "chunk_count": doc.chunk_count}


@router.get("")
def list_docs(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {"id": d.id, "filename": d.filename, "chunk_count": d.chunk_count, "uploaded_at": d.uploaded_at.isoformat()}
        for d in docs
    ]


@router.delete("/{doc_id}", status_code=204)
def delete_doc(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    doc = db.query(Document).filter_by(id=doc_id).one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    from qdrant_client.models import Filter, FieldCondition, MatchValue

    get_qdrant_client().delete(
        collection_name="matcha_knowledge",
        points_selector=Filter(must=[FieldCondition(key="source", match=MatchValue(value=doc.filename))]),
    )

    db.delete(doc)
    db.commit()

    log_admin_action(db, action="delete_doc", target=doc.filename, ip=request.client.host if request.client else "")
```

- [ ] **Step 5: Mount router in `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import admin_docs, health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest backend/tests/test_admin_docs.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/ingestion.py backend/app/routers/admin_docs.py backend/app/main.py backend/tests/test_admin_docs.py
git commit -m "feat(backend): add admin docs upload/list/delete endpoints"
```

---

### Task 12: Admin users endpoints (list/block/unblock)

**Files:**
- Create: `backend/app/routers/admin_users.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_admin_users.py`

**Interfaces:**
- Consumes: `app.auth.require_admin`, `app.auth.log_admin_action`,
  `app.db.models.User`, `Message`, `Favourite`
- Produces: `GET /admin/users`, `POST /admin/users/{id}/block`,
  `POST /admin/users/{id}/unblock`

- [ ] **Step 1: Write failing test `tests/test_admin_users.py`**

```python
from app.db.models import Favourite, Message, User


def test_list_users_requires_auth(client):
    assert client.get("/admin/users").status_code == 401


def test_list_users_returns_summary(client, db_session):
    user = User(telegram_user_id="1")
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
    assert body[0]["message_count"] == 1
    assert body[0]["favourites"] == ["matcha"]
    assert body[0]["blocked"] is False


def test_block_and_unblock_user(client, db_session):
    user = User(telegram_user_id="2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    block_response = client.post(f"/admin/users/{user.id}/block", auth=("admin", "admin"))
    assert block_response.status_code == 200
    db_session.refresh(user)
    assert user.blocked is True

    unblock_response = client.post(f"/admin/users/{user.id}/unblock", auth=("admin", "admin"))
    assert unblock_response.status_code == 200
    db_session.refresh(user)
    assert user.blocked is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_admin_users.py -v`
Expected: FAIL with `404 Not Found` / import error

- [ ] **Step 3: Write `app/routers/admin_users.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Favourite, Message, User

router = APIRouter(prefix="/admin/users")


@router.get("")
def list_users(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    users = db.query(User).order_by(User.first_seen.desc()).all()
    result = []
    for u in users:
        message_count = db.query(func.count(Message.id)).filter(Message.user_id == u.id).scalar()
        favourites = [f.drink_name for f in db.query(Favourite).filter_by(user_id=u.id).all()]
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
    return result


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter_by(id=user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/block")
def block_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.blocked = True
    db.commit()
    log_admin_action(db, action="block_user", target=user.telegram_user_id, ip=request.client.host if request.client else "")
    return {"id": user.id, "blocked": user.blocked}


@router.post("/{user_id}/unblock")
def unblock_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.blocked = False
    db.commit()
    log_admin_action(db, action="unblock_user", target=user.telegram_user_id, ip=request.client.host if request.client else "")
    return {"id": user.id, "blocked": user.blocked}
```

- [ ] **Step 4: Mount router in `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import admin_docs, admin_users, health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_admin_users.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/admin_users.py backend/app/main.py backend/tests/test_admin_users.py
git commit -m "feat(backend): add admin users list/block/unblock endpoints"
```

---

### Task 13: Admin logs endpoints (access + audit)

**Files:**
- Create: `backend/app/routers/admin_logs.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_admin_logs.py`

**Interfaces:**
- Consumes: `app.auth.require_admin`, `app.db.models.Message`,
  `app.db.models.AdminAuditLog`
- Produces: `GET /admin/logs/access?limit=&offset=`,
  `GET /admin/logs/audit?limit=&offset=`

- [ ] **Step 1: Write failing test `tests/test_admin_logs.py`**

```python
from app.db.models import AdminAuditLog, Message, User


def test_access_log_requires_auth(client):
    assert client.get("/admin/logs/access").status_code == 401


def test_access_log_returns_messages(client, db_session):
    user = User(telegram_user_id="3")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    response = client.get("/admin/logs/access", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["content"] == "hi"
    assert body[0]["telegram_user_id"] == "3"


def test_audit_log_returns_actions(client, db_session):
    db_session.add(AdminAuditLog(action="login"))
    db_session.commit()

    response = client.get("/admin/logs/audit", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["action"] == "login"


def test_logs_respect_limit_and_offset(client, db_session):
    for i in range(3):
        db_session.add(AdminAuditLog(action=f"action-{i}"))
    db_session.commit()

    response = client.get("/admin/logs/audit?limit=1&offset=1", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_admin_logs.py -v`
Expected: FAIL with `404 Not Found` / import error

- [ ] **Step 3: Write `app/routers/admin_logs.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.auth import require_admin
from app.db.base import get_db
from app.db.models import AdminAuditLog, Message

router = APIRouter(prefix="/admin/logs")


@router.get("/access")
def access_log(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(Message)
        .options(joinedload(Message.user))
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "telegram_user_id": m.user.telegram_user_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@router.get("/audit")
def audit_log(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "action": a.action,
            "target": a.target,
            "ip": a.ip,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]
```

- [ ] **Step 4: Mount router in `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import admin_docs, admin_logs, admin_users, health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
app.include_router(admin_logs.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_admin_logs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/admin_logs.py backend/app/main.py backend/tests/test_admin_logs.py
git commit -m "feat(backend): add admin access log and audit log endpoints"
```

---

### Task 14: Full test suite + audit-log-per-admin-call check

**Files:**
- Test: `backend/tests/test_admin_docs.py`, `test_admin_users.py` (extend
  with audit assertions)

**Interfaces:**
- Consumes: everything above

- [ ] **Step 1: Write failing test — append to `tests/test_admin_docs.py`**

```python
from app.db.models import AdminAuditLog


def test_upload_doc_writes_audit_log(client, db_session):
    from unittest.mock import MagicMock, patch

    fake_qdrant = MagicMock()
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]

    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant), patch(
        "app.routers.admin_docs.get_openai_client", return_value=fake_openai
    ):
        client.post(
            "/admin/docs",
            files={"file": ("a.txt", BytesIO(b"content"))},
            auth=("admin", "admin"),
        )

    logs = db_session.query(AdminAuditLog).filter_by(action="upload_doc").all()
    assert len(logs) == 1
    assert logs[0].target == "a.txt"
```

- [ ] **Step 2: Write failing test — append to `tests/test_admin_users.py`**

```python
from app.db.models import AdminAuditLog


def test_block_user_writes_audit_log(client, db_session):
    user = User(telegram_user_id="4")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client.post(f"/admin/users/{user.id}/block", auth=("admin", "admin"))

    logs = db_session.query(AdminAuditLog).filter_by(action="block_user").all()
    assert len(logs) == 1
    assert logs[0].target == "4"
```

- [ ] **Step 3: Run new tests to verify they pass** (no implementation
  change needed — `log_admin_action` calls already exist in Tasks 11-12;
  this task closes the loop by asserting the audit trail actually lands)

Run: `pytest backend/tests/test_admin_docs.py backend/tests/test_admin_users.py -v`
Expected: PASS

- [ ] **Step 4: Run the full backend test suite**

Run: `pytest backend/tests -v`
Expected: PASS, all tests green

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_admin_docs.py backend/tests/test_admin_users.py
git commit -m "test(backend): verify audit log written on doc upload and user block"
```

---

## Self-Review Notes

- Spec coverage: webhook + blocked-user skip (Task 10), agent 4-node
  pipeline with extract_favourite fire-and-forget (Tasks 5-10), admin
  docs/recipes (Task 11), admin users list/block/unblock (Task 12), access
  + audit logs (Task 13), audit-row-per-admin-call (Tasks 11-14) — all
  covered. Frontend and CI/CD are out of scope for this plan (separate
  plans).
- Type consistency checked: `AgentState` fields used consistently across
  Tasks 5-10; `run_agent` signature consumed identically in Task 10 as
  produced in Task 9.
