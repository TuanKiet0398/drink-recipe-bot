# Structured customer profile (GĐ2 of the matcha-bot enhancement roadmap)

## Problem

The bot currently infers exactly one kind of durable fact about a
customer: `Favourite` (a drink they seem to like). It has no place to
record the other facts a real consultant would remember and act on —
allergies, budget, or how sweet/icy they like their drinks — so a
customer who mentions a dairy allergy today gets no protection from
that fact once it scrolls out of the last-10-message window.

This is gap **G2** from the case study
(`design /matcha-bot-case-study.html`). Its completion criterion: *a
customer states an allergy today, and a month later the bot still
avoids recommending it without being told again* — which requires the
fact to survive independently of both the raw message history and the
rolling summary (GĐ1), since GĐ3's 30-day retention job will delete raw
messages entirely.

## Decisions locked in with the user

- **Trigger**: inline, per chat turn — a third fire-and-forget
  background task in `app/routers/webhook.py`, following the exact
  shape already established by `_extract_favourite_background` (GĐ0)
  and `_maybe_summarize_background` (GĐ1). Not batched — an allergy
  mentioned in one message must be recorded before the bot's *next*
  reply, not after a threshold of messages accumulates.
- **Storage shape**: one row per `(user_id, note_type)`, upserted —
  not an append-only log like `Favourite`. A customer restating their
  budget overwrites the old value; there's no need to keep prior
  values once superseded.
- **`note_type` is a fixed set of three**: `allergy`, `budget`,
  `sugar_ice_level` — exactly what the case study asks for. Adding a
  fourth type later is a small, additive change (extend the extraction
  prompt and the fixed set), not a schema change.

## Architecture

```
Per chat turn (existing flow, unchanged):
  fetch_history(state, db)
    -> last 10 Message rows (unchanged)
    -> conversation_summaries row -> state.summary (GĐ1, unchanged)
    -> NEW: all CustomerNote rows for user_id -> state.customer_notes
  retrieve() / generate()  -- unchanged, _build_system_prompt now also
                              includes state.customer_notes when present

After the reply is sent (existing background-task point, extended again):
  _extract_favourite_background(state, user.id)        -- unchanged
  _maybe_summarize_background(user.id)                  -- unchanged (GĐ1)
  _extract_customer_notes_background(state, user.id)    -- NEW, same pattern:
    extract_customer_notes(state, db, chat_client, model) [1 LLM call]
      -> JSON: {"allergy": str|null, "budget": str|null,
                "sugar_ice_level": str|null}
      -> for each non-null field: upsert CustomerNote(user_id, note_type)
```

`extract_customer_notes` mirrors `extract_favourite`'s shape — one LLM
call, a single structured JSON response, a silent no-op when nothing
matches — but with one difference: its prompt includes both
`state.incoming_text` and the customer's *currently known* notes
(`state.customer_notes`, already loaded by `fetch_history`), and asks
for the complete, updated value per field rather than just what's new
in this message. This is required by the upsert storage: see "Why
upsert, not append" below. The three fields are requested in one call
rather than three separate ones, keeping the added cost to at most one
extra LLM call per turn — the same cost `extract_favourite` already
adds today.

**Why upsert, not append**: unlike `Favourite` (where multiple inferred
favourites can coexist), each `note_type` represents a single current
fact — a customer has one budget, one sugar/ice preference at a time.
Multiple allergies mentioned across turns are folded into one string
value (the extraction prompt asks the LLM to return the complete,
combined set of allergies known so far, not just the new one — see
Error handling for what happens when that combination can't happen
correctly).

## Components touched

| File | Change |
|---|---|
| `app/db/models.py` | New `CustomerNote` model: `id` (PK), `user_id` (FK `users.id`), `note_type` (String), `value` (Text), `confidence` (String, default `"inferred"`), `source` (String, default `"chat"`), `created_at`, `updated_at` (default + `onupdate` `_now`, matching `LLMSettings`'s pattern). Unique index on `(user_id, note_type)`. |
| `migrations/versions/` | New Alembic migration creating `customer_notes` with that unique index. |
| `app/agent/state.py` | `AgentState` gains `customer_notes: dict[str, str] = Field(default_factory=dict)` (keyed by `note_type`). |
| `app/agent/nodes.py` | `fetch_history()` also loads all `CustomerNote` rows for the user into `state.customer_notes`. `_build_system_prompt()` renders a new section (same placement style as the GĐ1 summary section) when `state.customer_notes` is non-empty. New `extract_customer_notes(state, db, chat_client, model) -> None`: one LLM call, JSON-parsed, upserts each non-null field via a query-then-update-or-insert on `(user_id, note_type)`. |
| `app/routers/webhook.py` | Add `_extract_customer_notes_background(state, user_id)`, following `_extract_favourite_background`'s exact shape (own `SessionLocal()`, `asyncio.to_thread`, blanket `try/except` + `logger.exception`). Fire it as a third task alongside the other two at the existing call site. |

## System prompt rendering

The new section reads, when notes exist:

```
What we know about this customer: allergic to dairy; budget around 50k VND per order; likes it lightly sweet, extra ice.
```

Built from `state.customer_notes` in a fixed order (`allergy`, `budget`,
`sugar_ice_level`, skipping any type with no row), joined with `; `.
Placed directly after the GĐ1 summary section and before the
`favourites` line — allergy information needs to land before the model
reasons about what to recommend, and this ordering makes ignoring it in
the system prompt's later "only recommend from knowledge" instructions
much harder for the model to do by accident.

## Error handling

- `extract_customer_notes` LLM call fails, or returns malformed JSON:
  logged and swallowed — no `CustomerNote` row is touched that turn.
  This mirrors `extract_favourite`'s existing tolerance exactly (a
  malformed response degrades to "nothing learned this turn", never to
  a crashed background task).
- The extraction prompt explicitly instructs the LLM to return the
  **complete current value** for a field (e.g. all known allergies
  combined, not just what's newly mentioned) precisely because storage
  is upsert-only. This shifts the "don't lose an earlier allergy"
  responsibility into the prompt itself: `fetch_history`'s loaded
  `state.customer_notes` is included in the extraction call's input for
  this reason (unlike `extract_favourite`, which only looks at the
  incoming message) — the LLM sees the current stored value for a type
  and is told to return an updated superset, not a replacement, when
  the message doesn't contradict what's already known.
- A background-task failure never affects the chat reply already sent
  — same blanket `try/except` as the other two background tasks.

## Testing

- `fetch_history()` populates `state.customer_notes` from existing
  `CustomerNote` rows (keyed by `note_type`), and returns an empty dict
  when none exist.
- `_build_system_prompt()` includes the customer-notes section when
  `state.customer_notes` is non-empty, in the fixed
  allergy/budget/sugar_ice_level order, and omits the section entirely
  when empty.
- `extract_customer_notes()`:
  - a message mentioning an allergy creates one `CustomerNote(note_type="allergy")` row.
  - a second call for the same user with a restated/updated value
    updates the existing row (`(user_id, note_type)` stays unique —
    still exactly one row) rather than inserting a second one.
  - a message with no relevant information is a no-op (no rows
    touched).
  - malformed LLM output leaves existing notes untouched.
- Integration: a simulated conversation where an allergy is mentioned
  early, several unrelated turns follow, and a later turn asks for a
  recommendation — assert the system prompt still carries the allergy
  and the reply doesn't recommend the disallowed ingredient (mirrors
  GĐ1's UC3 regression test, but for UC4's "remembers a month later"
  claim).
- `_extract_customer_notes_background` wiring test in
  `tests/test_webhook.py`, mirroring the GĐ1 background-task test:
  process one message through `process_telegram_message`, await
  `_background_tasks`, assert the expected `CustomerNote` row exists.

## Out of scope

- Admin-facing UI to view or hand-edit a customer's notes — not
  requested; a future admin-dashboard spec can add this on top of the
  table this spec creates.
- Deduplicating or reconciling `CustomerNote` against `Favourite` or
  the GĐ1 `conversation_summaries` text — the three stay independent
  data sources; each is rendered as its own system-prompt section.
- The 30-day raw-message retention job (GĐ3) — it depends on
  `CustomerNote` existing (retention explicitly preserves
  `conversation_summaries` and `customer_notes`, only raw `Message`
  rows are deleted), but is its own spec.
- Structured typing/validation beyond free-text `value` (e.g. a
  numeric budget field, an enum for sugar/ice level) — the case study
  only asks that the bot remember and act on these facts in
  conversation, not that they be queryable/filterable structured data.
