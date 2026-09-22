---
status: completed
---

# Token-budget guard before generate()

**Mode:** `--port` (idiomatic rewrite of one mechanism — WeKnora is Go, this is Python).

**Source manifest:** local path `/mnt/d/Workspace/Project/WeKnora/` (Tencent WeKnora, Go monorepo). Local working tree read at plan time (2026-09-22), no git ref pinned.

**Source files read:** `internal/agent/token/estimator.go`, `internal/agent/compaction/settings.go`, `internal/agent/compaction/cutpoint.go`, `internal/agent/compaction/compactor.go` (read in the prior `/ak:xia` session on this repo).

**Target files:** `backend/app/agent/nodes.py` (new helper + `generate()` call site).

## Dependency matrix

| Component | Source | Local equivalent | Status |
|---|---|---|---|
| Token estimation | `token.Estimator` (tiktoken-go, calibrated scale) | none | NEW — simplified |
| Compaction trigger | `Settings.ShouldCompact` (token budget vs context window) | `maybe_summarize` threshold=20 messages (count, not tokens) | NEW (a different check — see below) |
| Cut point / tool-call pairing | `FindCutPoint` | N/A — no tool-call loop in this bot | OUT OF SCOPE |
| Checkpoint | `Checkpoint.TurnID` | `ConversationSummary.last_summarized_message_id` | Already equivalent |

## Decision matrix (accepted)

| Decision | WeKnora's way | Our way | Recommendation |
|---|---|---|---|
| Token estimation | `tiktoken-go` BPE + learned per-provider scale | none | Use `len(text) // 4` — the same fallback heuristic WeKnora's own `EstimateString` uses when its tokenizer call fails ("close enough to trigger... at roughly the right time" is their own stated bar). No new dependency, no scale-calibration loop (nothing here feeds it real `Usage` deltas the way a ReAct engine does). |
| What gets checked | Estimated context tokens vs `MaxContextTokens - ReserveTokens`, checked every round of a multi-round ReAct loop | Nothing — `generate()` assembles `[system] + state.history + [user]` and calls the LLM with no size check | Port the check itself: estimate the assembled `messages` list before the `generate()` call; this is the actual gap — `maybe_summarize`'s message-count threshold never looks at what `generate()` is about to send. |
| Cut point + tool-result pairing | Walks backward, never separates a tool call from its result, splits an oversized turn | N/A | Skip — this bot's history is plain `{role, content}` turns (`fetch_history`, `limit=10`), no tool-call chains to pair. |
| Context window source | Admin-configured `MaxContextTokens` per model in a model catalog | `LLMSettings.chat_model` is a free-text string (any OpenAI-compatible or Ollama model), no context-window registry | Don't build a model catalog for this. Use one conservative fixed budget (default 6000 tokens) that safely fits even a small local Ollama model window, with an env override for operators running a larger-context model. |

## Phase 1: token estimate + budget guard

**Files:** `backend/app/agent/nodes.py`

- [x] Add `_estimate_tokens(text: str) -> int` — `len(text) // 4`, matching WeKnora's own fallback heuristic.
- [x] Add `_estimate_message_tokens(message: dict) -> int` — `_estimate_tokens(message["content"]) + 4` (small per-message overhead, mirrors WeKnora's `perMessageOverhead`).
- [x] Add `MAX_PROMPT_TOKENS = int(os.environ.get("MAX_PROMPT_TOKENS", 6000))` module constant.
- [x] Add `_fit_history_to_budget(system_prompt: str, history: list[dict], incoming_text: str, budget: int) -> list[dict]`: estimates system + incoming first (fixed cost), then keeps as many of the **newest** history messages as fit the remaining budget, dropping the oldest first — mirrors `FindCutPoint`'s "keep the largest suffix that fits" logic, simplified (no tool-pairing needed since there's none here).
- [x] `generate()`: replaced `messages.extend(state.history)` with `messages.extend(_fit_history_to_budget(system_prompt, state.history, state.incoming_text, MAX_PROMPT_TOKENS))`. Logs (`logger.warning`) when trimming actually drops a message.
- [x] Test: `tests/test_agent_nodes.py` — `_fit_history_to_budget` drops oldest messages first when over budget and keeps everything when under; `generate()` sends a trimmed `messages` list when history is artificially oversized (long synthetic messages), and sends the full list unchanged when under budget.

## Verification

- Run `pytest backend/tests/` after the change — existing `generate()` tests use short fixture messages well under 6000 tokens, so trimming must not fire for them (regression check).
- No public API/contract change — `generate()`'s signature and `AgentState` are unaffected; this only changes what's inside the assembled `messages` list under a budget-exceeded condition that doesn't occur in current tests.

## Risk score: Low

Pure defensive addition — under the default budget, no existing conversation flow changes. The only behavior change is a graceful trim instead of an eventual provider `context_length_exceeded` error, which does not currently have any handling at all.

## Out of scope (per decision matrix)

- `tiktoken` dependency / real BPE counting — the char/4 heuristic is WeKnora's own admitted fallback bar.
- Tool-call/tool-result cut-point pairing and mid-turn splitting — this bot has no ReAct tool-call loop.
- Per-model context-window catalog — one fixed, env-overridable budget is enough for a single-shop-bot's model roster.
- Provider-side overflow *recovery* (WeKnora's `ReasonOverflow` repair path, triggered when the provider itself rejects a too-large request) — not implemented here since the guard is applied proactively before every call; add only if a real `context_length_exceeded` error is observed in production logs.
