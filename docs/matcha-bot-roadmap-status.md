# Matcha bot enhancement roadmap — status

Tracks completion of the 6-phase roadmap from `design /matcha-bot-case-study.html`
against gaps G1-G8. Written 2026-09-09, after merging the
`worktree-rolling-conversation-summary` branch into `main` (`88916cf`) and one
follow-up fix (`9d4e860`).

**All 6 phases done.**

| Phase | Gap | Status | Key files |
|---|---|---|---|
| GĐ1 — Rolling summary | G1 | ✅ Done | `backend/app/agent/nodes.py` (`fetch_history`, `summarize_conversation`, `maybe_summarize`), `conversation_summaries` table (migration `0005`) |
| GĐ2 — Customer profile | G2 | ✅ Done | `extract_customer_notes`, `customer_notes` table (migration `0006`) |
| GĐ3 — 30-day retention | G3, G4/G8 | ✅ Done | `backend/app/retention.py` (`purge_inactive_messages`, `run_retention_loop`), `users.last_active_at` (migration `0007`), wired into `app/main.py` lifespan |
| GĐ4 — Long-document ingestion | G5 | ✅ Done | `backend/app/ingestion.py` (`split_into_pieces`, `chunk_document` pre-split) |
| GĐ5 — Daily cost limit | G6 | ✅ Done | `LLMSettings.daily_token_limit` (migration `0008`), `get_daily_token_total`, webhook gate, Settings page field |
| GĐ6 — Editable personality | G7 | ✅ Done | `_load_soul` no longer cached, `/admin/soul` endpoint, `PersonalityPage.tsx` |

## Specs and plans on record

- `docs/superpowers/specs/2026-09-08-rolling-conversation-summary-design.md` + plan
- `docs/superpowers/specs/2026-09-08-customer-note-design.md` + plan
- `docs/superpowers/specs/2026-09-08-30-day-retention-design.md` + plan
- GĐ4/GĐ5/GĐ6 went through the **bounded** path (short in-chat design, approved, implemented directly) — no separate spec files; the design is recorded in this conversation's history and in the commit messages themselves.

## Test status (last full run)

- Backend: 248-250/250 pass. 2 known pre-existing failures in
  `tests/test_agent_clients.py` — caused by the local `backend/.env` holding a
  real `OPENAI_API_KEY` instead of the placeholder `test-key-not-real` these
  two tests expect (CI's `deploy.yml` sets that placeholder explicitly; the
  local dev `.env` doesn't). Not caused by this roadmap's changes, not fixed
  here — fixing it means either not using a real key for local dev testing or
  updating those two tests, both outside this roadmap's scope.
- Frontend: 56/58 pass. 2 known pre-existing failures in `tests/App.test.tsx`
  and `tests/welcome/WelcomePage.test.tsx` — confirmed via `git stash` to fail
  identically before any of this roadmap's changes. Unrelated, not fixed here.
- One flaky backend test observed intermittently during development:
  `test_process_message_background_favourite_extraction_actually_runs` (and
  occasionally its `customer_note` sibling) — passes on rerun every time it
  was seen; looks like async/event-loop timing in the test harness, not a
  real bug. Not investigated further; flagged here for whoever picks it up.

## Migrations

`0001` → `0008`, all verified with `alembic upgrade head` from a clean
`local.db` on `main` after merge.

## Explicitly out of scope (per the design docs, not overlooked)

- Admin UI to view/edit a customer's rolling summary or CustomerNote fields directly.
- Configurable retention window (fixed at 30 days) or configurable summarization threshold via UI (fixed at 20 messages / 10-message raw window in code).
- Structured (typed/validated) CustomerNote values — stored as free text.
- Deduplication between `Favourite`, `ConversationSummary`, and `CustomerNote`.
- Terraform infra has not been `apply`'d from this workspace (no local `.tfstate`) — the roadmap work never touched `infra/`, this was pre-existing/unrelated.

## Follow-ups worth a look, not blockers

- The `NaN`-guard fix on the Settings page's daily token limit field
  (`9d4e860`) was applied after an ad hoc code review of the GĐ5/GĐ6
  frontend diff; no other findings from that review needed action.
- The two pre-existing test failures (backend `.env` mismatch, frontend
  Welcome/App tests) are unrelated to this roadmap but sitting on `main` —
  worth a separate look if they matter to CI health.
