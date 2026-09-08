# Structured Customer Profile (CustomerNote) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the matcha bot a durable, structured record of three customer facts — allergy, budget, sugar/ice preference — that survives independently of raw chat history and the rolling summary, so the bot keeps acting on them weeks later without being told again.

**Architecture:** New `customer_notes` table, one row per `(user_id, note_type)`, upserted. A new `extract_customer_notes()` (one LLM call per turn, structured JSON over the three fixed fields) runs as a third fire-and-forget background task in `app/routers/webhook.py`, alongside the existing `_extract_favourite_background` and `_maybe_summarize_background` tasks. `fetch_history()` loads the rows into `AgentState.customer_notes`; `_build_system_prompt()` renders them ahead of the recommendation instructions.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest (existing `db_session`/`channel_id` fixtures in `tests/conftest.py`), OpenAI-compatible chat client (existing `retry_once`/`log_token_usage` helpers — note `extract_favourite`, the closest existing analogue, does *not* use `retry_once`, and this plan follows that same precedent rather than introducing it here).

**Spec:** `docs/superpowers/specs/2026-09-08-customer-note-design.md`

## Global Constraints

- `note_type` is a fixed set of exactly three values: `allergy`, `budget`, `sugar_ice_level` — no other types are extracted or rendered.
- Storage is upsert-only: at most one `customer_notes` row per `(user_id, note_type)`, never an append-only log.
- The extraction prompt must include the customer's *currently known* notes (not just the incoming message) and ask for the complete updated value per field, so an upsert never silently drops an earlier fact the new message doesn't repeat.
- Trigger is inline per chat turn (a background task fired after each reply, same pattern as `_extract_favourite_background`), not batched.
- A failure anywhere in extraction or storage must never affect the chat reply already sent to the user.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/db/models.py` | Add `CustomerNote` model. |
| `migrations/versions/0006_customer_notes.py` | New Alembic migration creating the table with a unique `(user_id, note_type)` index. |
| `app/agent/state.py` | `AgentState` gains `customer_notes: dict[str, str]`. |
| `app/agent/nodes.py` | `fetch_history()` loads notes into the dict; `_build_system_prompt()` renders them; new `extract_customer_notes()` (LLM call + upsert). |
| `app/routers/webhook.py` | New `_extract_customer_notes_background(state, user_id)`, fired alongside the other two background tasks. |
| `tests/test_models.py` | Model-level test for `CustomerNote`'s unique constraint. |
| `tests/test_agent_nodes.py` | Tests for `fetch_history` note loading, `_build_system_prompt` note rendering, `extract_customer_notes`. |
| `tests/test_webhook.py` | Test that the new background task actually runs and persists a note. |

---

### Task 1: `CustomerNote` model + migration

**Files:**
- Modify: `app/db/models.py`
- Create: `migrations/versions/0006_customer_notes.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `CustomerNote` (SQLAlchemy model) with columns `id: int` (PK), `user_id: int` (FK `users.id`), `note_type: str`, `value: str`, `confidence: str` (default `"inferred"`), `source: str` (default `"chat"`), `created_at: datetime`, `updated_at: datetime` (default + onupdate `_now`), and a unique index on `(user_id, note_type)`. Later tasks import this from `app.db.models`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` (it already imports `ConversationSummary`, `Favourite`, `Message`, `User` from `app.db.models` — extend that import line):

```python
from app.db.models import AdminAuditLog, Channel, ConversationSummary, CustomerNote, Document, Favourite, Message, User
```

```python
def test_customer_note_unique_per_user_and_type(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(CustomerNote(user_id=user.id, note_type="allergy", value="dairy"))
    db_session.commit()

    row = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="allergy").one()
    assert row.value == "dairy"
    assert row.confidence == "inferred"
    assert row.source == "chat"
    assert row.updated_at is not None


def test_customer_note_rejects_a_second_row_for_the_same_user_and_type(db_session, channel_id):
    from sqlalchemy.exc import IntegrityError

    user = User(channel_id=channel_id, telegram_user_id="cn2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="50k"))
    db_session.commit()

    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="60k"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py -k customer_note -v`
Expected: FAIL with `ImportError: cannot import name 'CustomerNote'`

- [ ] **Step 3: Add the model**

In `app/db/models.py`, add after the `ConversationSummary` class:

```python
class CustomerNote(Base):
    __tablename__ = "customer_notes"
    __table_args__ = (
        Index("ix_customer_notes_user_id_note_type", "user_id", "note_type", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    note_type: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String, default="inferred")
    source: Mapped[str] = mapped_column(String, default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
```

(`Index` is already imported in `app/db/models.py` — it's used by `User`'s
`ix_users_channel_id_telegram_user_id` constraint.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models.py -k customer_note -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Create `migrations/versions/0006_customer_notes.py`:

```python
"""add customer_notes table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False, server_default="inferred"),
        sa.Column("source", sa.String(), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_customer_notes_user_id_note_type",
        "customer_notes",
        ["user_id", "note_type"],
        unique=True,
    )
    op.create_index("ix_customer_notes_user_id", "customer_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_notes_user_id", table_name="customer_notes")
    op.drop_index("ix_customer_notes_user_id_note_type", table_name="customer_notes")
    op.drop_table("customer_notes")
```

- [ ] **Step 6: Verify the migration applies cleanly**

Run: `cd backend && rm -f local.db && alembic upgrade head && alembic current && rm -f local.db`
Expected: no errors, `alembic current` reports `0006 (head)`

- [ ] **Step 7: Commit**

```bash
git add app/db/models.py migrations/versions/0006_customer_notes.py tests/test_models.py
git commit -m "feat: add customer_notes table"
```

---

### Task 2: `AgentState.customer_notes` field

**Files:**
- Modify: `app/agent/state.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `AgentState.customer_notes: dict[str, str] = Field(default_factory=dict)`. Task 3 sets it; `_build_system_prompt` (Task 3) reads it.

- [ ] **Step 1: Add the field**

In `app/agent/state.py`, add to `AgentState` (next to `summary`, since both are "known-about-the-user" context loaded by `fetch_history`):

```python
    customer_notes: dict[str, str] = Field(default_factory=dict)
```

The full class becomes:

```python
class AgentState(BaseModel):
    user_id: int
    chat_id: str
    incoming_text: str
    history: list[dict] = Field(default_factory=list)
    favourites: list[str] = Field(default_factory=list)
    summary: str | None = None
    customer_notes: dict[str, str] = Field(default_factory=dict)
    retrieved_chunks: list[str] = Field(default_factory=list)
    reply: str = ""
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd backend && pytest tests/test_agent_nodes.py tests/test_agent_graph.py -v`
Expected: PASS (new field has a default, so no existing `AgentState(...)` construction breaks)

- [ ] **Step 3: Commit**

```bash
git add app/agent/state.py
git commit -m "feat: add AgentState.customer_notes field"
```

---

### Task 3: `fetch_history` loads notes; `_build_system_prompt` renders them

**Files:**
- Modify: `app/agent/nodes.py`
- Test: `tests/test_agent_nodes.py`

**Interfaces:**
- Consumes: `CustomerNote` (Task 1), `AgentState.customer_notes` (Task 2).
- Produces: `fetch_history()` sets `state.customer_notes`; `_build_system_prompt()` includes them in the returned prompt string, in the fixed order `allergy`, `budget`, `sugar_ice_level`, when non-empty. Task 4 (`extract_customer_notes`) is what actually populates the rows `fetch_history` reads.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_agent_nodes.py` (extend the existing `from app.db.models import ...` line to add `CustomerNote`):

```python
from app.db.models import ConversationSummary, CustomerNote, Favourite, Message, User
```

```python
def test_fetch_history_loads_customer_notes(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="210")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(CustomerNote(user_id=user.id, note_type="allergy", value="dairy"))
    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="50k VND"))
    db_session.commit()

    state = AgentState(user_id=user.id, chat_id="210", incoming_text="what's good today?")
    result = fetch_history(state, db_session)

    assert result.customer_notes == {"allergy": "dairy", "budget": "50k VND"}


def test_fetch_history_customer_notes_empty_when_no_rows_exist(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="211")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="211", incoming_text="hi")
    result = fetch_history(state, db_session)

    assert result.customer_notes == {}


def test_build_system_prompt_includes_customer_notes_in_fixed_order():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="hi",
        customer_notes={
            "sugar_ice_level": "light sugar, extra ice",
            "allergy": "dairy",
            "budget": "50k VND per order",
        },
    )
    prompt = nodes._build_system_prompt(state)

    assert "What we know about this customer:" in prompt
    allergy_pos = prompt.index("dairy")
    budget_pos = prompt.index("50k VND per order")
    sugar_pos = prompt.index("light sugar, extra ice")
    assert allergy_pos < budget_pos < sugar_pos


def test_build_system_prompt_omits_customer_notes_section_when_empty():
    state = AgentState(user_id=1, chat_id="1", incoming_text="hi")
    prompt = nodes._build_system_prompt(state)
    assert "What we know about this customer" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_nodes.py -k "customer_notes" -v`
Expected: FAIL (`fetch_history` doesn't set `.customer_notes`; `_build_system_prompt` doesn't render it)

- [ ] **Step 3: Implement**

In `app/agent/nodes.py`, update the import:

```python
from app.db.models import ConversationSummary, CustomerNote, Favourite, Message
```

Update `fetch_history` (append after the existing `state.summary = ...` line, before `return state`):

```python
    note_rows = db.execute(
        select(CustomerNote).where(CustomerNote.user_id == state.user_id)
    ).scalars().all()
    state.customer_notes = {row.note_type: row.value for row in note_rows}

    return state
```

Update `_build_system_prompt`:

```python
def _build_system_prompt(state: AgentState) -> str:
    favourites = ", ".join(state.favourites) or "none known yet"
    context = "\n".join(f"- {chunk}" for chunk in state.retrieved_chunks) or "(no matching knowledge found)"
    soul = _load_soul()
    soul_section = f"{soul}\n\n" if soul else ""
    summary_section = (
        f"What we know from earlier in this conversation: {state.summary}\n\n" if state.summary else ""
    )
    notes_section = ""
    if state.customer_notes:
        ordered_labels = {
            "allergy": "allergic to",
            "budget": "budget around",
            "sugar_ice_level": "likes it",
        }
        parts = [
            f"{ordered_labels[note_type]} {state.customer_notes[note_type]}"
            for note_type in ("allergy", "budget", "sugar_ice_level")
            if note_type in state.customer_notes
        ]
        notes_section = f"What we know about this customer: {'; '.join(parts)}.\n\n"
    return (
        f"{soul_section}"
        f"{summary_section}"
        f"{notes_section}"
        "You are a premium matcha and tea ceremony consultant for this specific shop. "
        f"The user's known favourite drinks: {favourites}. "
        f"Relevant knowledge (this is everything the shop actually offers — only recommend from this):\n{context}\n"
        "Only recommend or describe drinks/recipes that appear in the knowledge above. "
        "If the user asks about something not covered there, say the shop doesn't currently "
        "have that, and suggest one of the drinks from the knowledge above instead. "
        "Never invent a drink, ingredient, or brewing method that isn't in the knowledge — "
        "not even from your own general knowledge of drinks outside this shop. "
        "If the knowledge above says '(no matching knowledge found)', you MUST tell the user "
        "the shop doesn't have a recipe for that and offer to suggest something from what the "
        "shop does have — do not describe how to make the drink they asked about under any "
        "circumstances in that case."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_nodes.py -k "customer_notes" -v`
Expected: PASS

- [ ] **Step 5: Run the full node test file to check for regressions**

Run: `cd backend && pytest tests/test_agent_nodes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/agent/nodes.py tests/test_agent_nodes.py
git commit -m "feat: load and render structured customer notes"
```

---

### Task 4: `extract_customer_notes()` — LLM extraction + upsert

**Files:**
- Modify: `app/agent/nodes.py`
- Test: `tests/test_agent_nodes.py`

**Interfaces:**
- Consumes: `CustomerNote` (Task 1), `AgentState.customer_notes` (Task 2, already populated by `fetch_history` before this runs in the real flow — see Task 5).
- Produces: `extract_customer_notes(state: AgentState, db: Session, chat_client, model: str) -> None`. Task 5 (`webhook.py`) calls this from the new background task.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_agent_nodes.py`:

```python
from app.agent.nodes import extract_customer_notes


def test_extract_customer_notes_creates_a_row_when_a_field_is_detected(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn10")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(
        user_id=user.id, chat_id="cn10", incoming_text="I'm allergic to dairy, please avoid it"
    )
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"allergy": "dairy", "budget": None, "sugar_ice_level": None})
            )
        )
    ]

    extract_customer_notes(state, db=db_session, chat_client=fake_openai, model="gpt-4o-mini")

    row = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="allergy").one()
    assert row.value == "dairy"
    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 1


def test_extract_customer_notes_updates_existing_row_instead_of_inserting_a_second_one(
    db_session, channel_id
):
    user = User(channel_id=channel_id, telegram_user_id="cn11")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="50k VND"))
    db_session.commit()

    state = AgentState(
        user_id=user.id,
        chat_id="cn11",
        incoming_text="actually let's go up to 80k",
        customer_notes={"budget": "50k VND"},
    )
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"allergy": None, "budget": "80k VND", "sugar_ice_level": None})
            )
        )
    ]

    extract_customer_notes(state, db=db_session, chat_client=fake_openai, model="gpt-4o-mini")

    rows = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="budget").all()
    assert len(rows) == 1
    assert rows[0].value == "80k VND"


def test_extract_customer_notes_noop_when_nothing_detected(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn12")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="cn12", incoming_text="what time do you close?")
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"allergy": None, "budget": None, "sugar_ice_level": None})
            )
        )
    ]

    extract_customer_notes(state, db=db_session, chat_client=fake_openai, model="gpt-4o-mini")

    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 0


def test_extract_customer_notes_swallows_malformed_llm_output(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn13")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="cn13", incoming_text="hi")
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="not json"))
    ]

    extract_customer_notes(state, db=db_session, chat_client=fake_openai, model="gpt-4o-mini")

    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_nodes.py -k "extract_customer_notes" -v`
Expected: FAIL with `ImportError: cannot import name 'extract_customer_notes'`

- [ ] **Step 3: Implement**

In `app/agent/nodes.py`, add after `extract_favourite`:

```python
_CUSTOMER_NOTE_TYPES = ("allergy", "budget", "sugar_ice_level")


def extract_customer_notes(state: AgentState, db: Session, chat_client, model: str) -> None:
    """Extracts any of the three fixed customer-profile facts mentioned in
    the incoming message and upserts them into `customer_notes`. The prompt
    includes the customer's currently known notes and asks for the complete
    updated value per field — required because storage is upsert-only, so
    a value the LLM returns replaces (rather than merges with) what's
    stored. Silently no-ops on a malformed or empty LLM response, same
    tolerance as `extract_favourite`."""
    known = state.customer_notes or {}
    prompt = (
        "Extract the customer's allergy, budget, and sugar/ice preference "
        "from this message, if mentioned. What's already known about this "
        f"customer: {known or '(nothing yet)'}.\n\n"
        f"New message: {state.incoming_text!r}\n\n"
        "For each field, respond with the complete, updated value (combining "
        "anything already known with anything new in this message), or null "
        "if that field isn't known at all. Respond with strict JSON: "
        '{"allergy": "<value>" or null, "budget": "<value>" or null, '
        '"sugar_ice_level": "<value>" or null}.'
    )
    response = chat_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    log_token_usage(db, state.user_id, "extract_customer_notes", model, response.usage)
    try:
        parsed = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return

    for note_type in _CUSTOMER_NOTE_TYPES:
        value = parsed.get(note_type)
        if not value:
            continue
        existing = db.execute(
            select(CustomerNote).where(
                CustomerNote.user_id == state.user_id, CustomerNote.note_type == note_type
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(CustomerNote(user_id=state.user_id, note_type=note_type, value=value))
        else:
            existing.value = value
    db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_nodes.py -k "extract_customer_notes" -v`
Expected: PASS

- [ ] **Step 5: Run the full node test file to check for regressions**

Run: `cd backend && pytest tests/test_agent_nodes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/agent/nodes.py tests/test_agent_nodes.py
git commit -m "feat: add extract_customer_notes LLM extraction and upsert"
```

---

### Task 5: Wire into the webhook background-task flow

**Files:**
- Modify: `app/routers/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `extract_customer_notes` (Task 4, imported from `app.agent.nodes`), `get_chat_client`/`get_chat_model` (already imported in `webhook.py`), the existing `_background_tasks` set and background-task-function pattern (`_extract_favourite_background`, `_maybe_summarize_background`).
- Produces: nothing further downstream — this is the last task, it makes the feature live end-to-end.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_webhook.py` (mirrors `test_process_message_background_summarization_actually_runs`, already in this file from the GĐ1 plan):

```python
@pytest.mark.asyncio
async def test_process_message_background_customer_note_extraction_actually_runs(
    db_session, channel_id
):
    from tests.conftest import TestSessionLocal
    from app.db.models import CustomerNote

    user = User(channel_id=channel_id, telegram_user_id="999")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"allergy": "peanuts", "budget": None, "sugar_ice_level": None})
            )
        )
    ]

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=fake_openai),
        patch("app.routers.webhook.get_embedding_client", return_value=fake_openai),
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "999", "999", "I have a peanut allergy", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    row = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="allergy").one()
    assert row.value == "peanuts"
```

(This test file already has `import json` — check the top of `tests/test_webhook.py`; if it doesn't, add `import json` alongside the existing `import asyncio` line.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_webhook.py::test_process_message_background_customer_note_extraction_actually_runs -v`
Expected: FAIL (no `CustomerNote` row is ever created — nothing calls `extract_customer_notes` yet)

- [ ] **Step 3: Implement**

In `app/routers/webhook.py`, update the import:

```python
from app.agent.nodes import extract_customer_notes, extract_favourite, maybe_summarize
```

Add the new background function after `_maybe_summarize_background`:

```python
async def _extract_customer_notes_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_customer_notes makes a blocking OpenAI call; run it off
        # the event loop thread so it doesn't stall other concurrent
        # requests.
        await asyncio.to_thread(
            extract_customer_notes,
            state,
            db=db,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("extract_customer_notes failed for user_id=%s", user_id)
    finally:
        db.close()
```

At the existing background-task call site, fire the third task alongside the other two:

```python
    favourite_task = asyncio.create_task(_extract_favourite_background(state, user.id))
    _background_tasks.add(favourite_task)
    favourite_task.add_done_callback(_background_tasks.discard)

    summarize_task = asyncio.create_task(_maybe_summarize_background(user.id))
    _background_tasks.add(summarize_task)
    summarize_task.add_done_callback(_background_tasks.discard)

    customer_notes_task = asyncio.create_task(_extract_customer_notes_background(state, user.id))
    _background_tasks.add(customer_notes_task)
    customer_notes_task.add_done_callback(_background_tasks.discard)

    return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_webhook.py::test_process_message_background_customer_note_extraction_actually_runs -v`
Expected: PASS

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add app/routers/webhook.py tests/test_webhook.py
git commit -m "feat: trigger customer note extraction after each chat turn"
```

---

## Final Verification

- [ ] Run the full suite once more: `cd backend && pytest -v`
- [ ] Run `rm -f local.db && alembic upgrade head && alembic current` to confirm migration `0006` applies on top of `0005` cleanly, then `rm -f local.db`
- [ ] Manual sanity check (optional, if a local bot token is available): tell the bot an allergy, wait for the background task, ask an unrelated question, then ask for a recommendation and confirm the disallowed ingredient is avoided without re-stating the allergy
