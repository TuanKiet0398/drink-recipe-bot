# Rolling conversation summary (GĐ1 of the matcha-bot enhancement roadmap)

## Problem

`fetch_history()` (`app/agent/nodes.py:34`) pulls exactly the last 10
`Message` rows for a user and nothing else. Past 10 messages in a single
deep-dive conversation, the bot has no memory of anything said earlier in
that same session — the exact risk the original brief calls out (UC3):
long product-consultation conversations must not lose context or blow up
token cost by sending the full history on every turn.

This is gap **G1** from the case study
(`design /matcha-bot-case-study.html`): no summarization of aging-out
history. It's the foundation gap — GĐ2 (customer profile) and GĐ3
(30-day retention) both build on the mechanism this spec introduces.

## Decisions locked in with the user

- **Trigger mechanism**: inline, no new job/scheduler infrastructure.
  The repo has none today (no Celery/APScheduler/cron), and the existing
  `extract_favourite` flow already proves the right pattern: a
  fire-and-forget `asyncio` background task kicked off after the reply is
  sent (`app/routers/webhook.py:174-176`), off the response-latency path.
  Summarization reuses that same pattern rather than introducing a
  ticker/poller.
- **Storage shape**: one row per user (`conversation_summaries`), not one
  row per session — matches the existing per-user `Message`/`Favourite`
  model, and this bot has no session boundary concept to key on.
- **Cursor-based, not full-replay**: track `last_summarized_message_id`
  and only fold in messages newer than that cursor on each run (idea
  ported from goclaw's `channelmemory` unprocessed-message cursor) —
  avoids re-summarizing the same messages every time the threshold fires.
- **Batch threshold, not per-message**: summarization only runs when
  enough messages have aged out of the raw-10 window to be worth a batch
  LLM call — cost stays proportional to conversation *volume*, not to
  every single turn.

## Architecture

Two concepts stay separate and both feed the system prompt:

- **Raw window** — the most recent 10 messages, sent verbatim exactly as
  today. Unchanged behavior.
- **Rolling summary** — one row per user in a new `conversation_summaries`
  table, covering everything older than the raw window.

```
Per chat turn (existing flow, unchanged):
  fetch_history(state, db)
    -> last 10 Message rows (as today)
    -> NEW: load conversation_summaries row for user_id, set state.summary
  retrieve() / generate()  -- unchanged, _build_system_prompt now also
                              includes state.summary when present

After the reply is sent (existing background-task point, extended):
  _extract_favourite_background(state, user.id)   -- unchanged
  _maybe_summarize_background(user.id)             -- NEW, same pattern:
    count messages older than the raw-10 window and newer than
    last_summarized_message_id
    if count >= SUMMARY_THRESHOLD (20):
      summarize_conversation(old_summary_text, batch_of_messages) [1 LLM call]
      upsert conversation_summaries: summary_text = merged result,
                                      last_summarized_message_id = cutoff id
```

**Boundary math**: on each background run, find the id of the 10th most
recent message for the user (`raw_window_cutoff_id`). The messages
eligible for summarization are those with
`last_summarized_message_id < id <= raw_window_cutoff_id`. If that count
is `>= 20`, summarize exactly that batch, then move the cursor to
`raw_window_cutoff_id`. Below threshold, do nothing — those messages
stay un-summarized (but still outside the raw-10 window, i.e.
temporarily invisible to the bot) until enough accumulate. This bounds
LLM calls to roughly 1 per 20 aged-out messages, not 1 per turn.

**Merge, don't append**: each run's prompt includes the *existing*
`summary_text` (may be empty) plus the new batch, and instructs the LLM
to return one updated, bounded-length summary — not the old summary with
the new batch's summary concatenated. This is what keeps `summary_text`
from growing unboundedly across many merge cycles over a long-lived
customer relationship. The summarization prompt caps output at roughly
250 words and asks for durable facts only (preferences mentioned,
constraints/allergies, decisions made, products discussed) — small talk
and resolved back-and-forth get dropped on every merge.

## Components touched

| File | Change |
|---|---|
| `app/db/models.py` | New `ConversationSummary` model: `user_id` (PK, FK `users.id`, one row per user), `summary_text` (Text, default `""`), `last_summarized_message_id` (FK `messages.id`, nullable), `updated_at`. |
| `migrations/versions/` | New Alembic migration creating `conversation_summaries`. |
| `app/agent/state.py` | `AgentState` gains `summary: str \| None = None`. |
| `app/agent/nodes.py` | `fetch_history()` also loads the user's `ConversationSummary` row (if any) into `state.summary`. `_build_system_prompt()` includes a summary section, right before the favourites line, only when `state.summary` is truthy. New `summarize_conversation(old_summary, messages, chat_client, model, db, user_id) -> str` (same shape as `rewrite_query`/`rerank`: `retry_once`-wrapped, `log_token_usage(..., call_type="summarize_conversation", ...)`, returns `old_summary` unchanged on failure). New `maybe_summarize(db, user_id, chat_client, model, threshold=20) -> None` implementing the boundary math above and the upsert. |
| `app/routers/webhook.py` | Add `_maybe_summarize_background(user_id)`, following the exact shape of `_extract_favourite_background` (own `SessionLocal()`, `asyncio.to_thread`, blanket `try/except` + `logger.exception`). Fire it as a second task alongside the existing `_extract_favourite_background` task at the same call site (`webhook.py:174-176`). |

## Error handling

- `summarize_conversation` LLM call fails (after `retry_once`): return the
  old summary unchanged, don't move the cursor — the same messages are
  simply re-attempted on the next turn that crosses the threshold check,
  no data is lost.
- `maybe_summarize` itself wrapped in the same blanket
  `try/except` + `logger.exception` the background-task pattern already
  uses — a summarization failure never affects the chat reply already
  sent to the user.
- Race between two turns from the same user firing background tasks
  close together: acceptable to leave unhandled for v1 — Telegram
  messages from one user arrive effectively sequentially in practice, and
  a rare double-run just means one run's cursor update makes the other a
  no-op (it recomputes the same boundary and finds `count < threshold` or
  re-summarizes an already-summarized batch harmlessly, since the merge
  prompt just gets the same content twice).

## Testing

- `fetch_history()` populates `state.summary` from an existing
  `ConversationSummary` row, and leaves it `None` when no row exists yet.
- `_build_system_prompt()` includes the summary text when present, omits
  the section entirely when `state.summary` is `None`.
- `maybe_summarize()`:
  - does nothing when aged-out message count is below `SUMMARY_THRESHOLD`.
  - summarizes and upserts when at/above threshold, moving the cursor to
    the correct boundary id.
  - on LLM failure, leaves `summary_text` and the cursor unchanged.
  - a second run before new messages age out is a no-op (cursor already
    at the current boundary).
- Integration: a simulated 25+ message conversation for one user still
  produces a coherent reply referencing an early fact (e.g. an allergy
  mentioned in message 2), verifying the summary path actually reaches
  the model — this is the regression test for the original UC3 gap.
- Multi-cycle merge test: run `maybe_summarize` repeatedly across a very
  long simulated conversation (several threshold crossings) and assert
  `summary_text` length stays roughly bounded rather than growing with
  each cycle — this is the specific risk flagged during design.

## Out of scope

- Admin-facing UI to view or hand-edit a user's summary — not requested,
  no use case calls for it yet.
- Structured customer profile (allergies, budget, sugar/ice level as
  discrete fields) — that's GĐ2 (`CustomerNote`), a separate spec that
  builds on this one's background-task pattern and cursor idea.
- The 30-day raw-message retention job (GĐ3) — depends on this table
  existing (retention keeps `conversation_summaries`, deletes raw
  `Message` rows), but is its own spec.
- Deduplicating summary content against the existing `Favourite` table —
  the two stay independent for now; `Favourite` keeps its own inference
  path unchanged.
