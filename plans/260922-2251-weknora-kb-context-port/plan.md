---
status: completed
---

# Port WeKnora KB/context ideas into matcha bot backend

**Mode:** `--port` (idiomatic rewrite — literal `--copy` is not possible, source is Go, target is Python/FastAPI/Chroma).

**Source manifest:** local path `/mnt/d/Workspace/Project/WeKnora/` (Tencent WeKnora, Go monorepo). No git ref pinned — local working tree read at plan time (2026-09-22).

**Source files read:**
- `internal/infrastructure/chunker/strategy.go`
- `internal/application/service/knowledgebase_search_fusion.go`
- `internal/agent/compaction/compactor.go`
- `internal/modelcontext/` (dir listing only)

**Target files:** `backend/app/ingestion.py`, `backend/app/agent/nodes.py`, `backend/app/agent/state.py`.

## Dependency matrix

| Component | Source | Local equivalent | Status |
|---|---|---|---|
| Chunking | `chunker.Split` tiered strategy chain | `ingestion.chunk_document` (single LLM call + naive fallback) | EXISTS, extend |
| Retrieval fusion | `fuseWithRRF` (vector+keyword) | `nodes.retrieve` (vector-only) | NEW (keyword side) |
| Context compaction | `Compactor.Compact` (token-budget, checkpoint, degrade) | `nodes.maybe_summarize`/`summarize_conversation` (threshold-batch merge) | EXISTS, already implements the goal — see Phase 2 |
| Citations | `modelcontext` resource/citation registry | none — `retrieved_chunks: list[str]` has no metadata | NEW |

## Decision matrix (accepted)

| Decision | Source's way | Our way | Recommendation |
|---|---|---|---|
| Chunking resilience | Multi-tier heading/heuristic/legacy chain w/ validator | One LLM call per piece, naive fallback only | Add one retry tier: naive-chunk retry with a smaller `max_chars` before falling to word-count split, validated by chunk-count/coverage check |
| Compaction resilience | Degrade to raw archive on LLM failure | Falls back to unchanged old summary, cursor untouched, retried next run | Current design already prevents data loss (batch just retries). Port only the missing observability: mark/alert when a batch has failed repeatedly, since WeKnora's `Degraded` flag exists precisely so callers can see this |
| Citations | Structured resource handles | Flat text list, no metadata | Port: surface `filename`/`document_id` alongside each retrieved chunk (already stored in Chroma metadata but discarded) |
| Hybrid retrieval | RRF fuses vector + BM25 keyword | Vector-only | Port RRF fusion math; keyword side implemented as in-process BM25 over the same Chroma collection's documents (no new service — corpus is small, a shop KB) |

## Phase 1: Chunking fallback tier

**Files:** `backend/app/ingestion.py`

- [x] In `chunk_document`, when `_chunk_via_llm` raises for a piece, retry that single piece once with `max_chars` halved (catches pieces too large/malformed for one LLM call) before the whole-document fallback to `chunk_text`.
- [x] Add a coverage validator: reject an LLM chunking result if the concatenated `original_text` length is < 50% of the input piece length (mirrors WeKnora's `ValidateChunks` coverage check) — on rejection, fall through same as an exception.
- [x] Test: `tests/test_ingestion.py` — assert retry path triggers on first-call failure, and coverage-rejection falls through to naive chunker.

## Phase 2: Summarization stuck-batch observability

**Files:** `backend/app/agent/nodes.py`, `backend/app/metrics.py`

- [x] `maybe_summarize`: track consecutive-failure count (new column `ConversationSummary.failed_attempts: int default 0`, migration `0014_summary_failed_attempts.py` — `backend/local.db` backed up first, per project DB rule). Increment on failure, reset to 0 on `"ran"`.
- [x] Once `failed_attempts` reaches `STUCK_SUMMARIZE_ATTEMPTS` (3), emit `record_summarize("stuck")` via the existing `SUMMARIZE_RUNS` counter (no new metric/gauge needed — the existing counter already has an `outcome` label, so `stuck` is queryable in the existing Grafana panel without a dashboard change).
- [x] Test: `tests/test_agent_nodes.py` — failed_attempts increments across repeated failed calls, resets on success, `"stuck"` fires at the threshold.

## Phase 3: Citation metadata on retrieved chunks

**Files:** `backend/app/agent/state.py`, `backend/app/agent/nodes.py`

- [x] `AgentState`: add `retrieved_sources: list[dict] = Field(default_factory=list)` (parallel to `retrieved_chunks`) — `retrieved_chunks` stays `list[str]` unchanged so `check_facts`/`extract_recommendation`/`generate` need no changes.
- [x] `retrieve()`: fetch metadata alongside `documents`/`distances` (already returned by Chroma, previously discarded), build `state.retrieved_sources` keyed the same as `best_scores`, reordered to match the final reranked `retrieved_chunks` order.
- [x] `_build_system_prompt`: append a compact source line per knowledge bullet, e.g. `- {chunk} (from: {filename})`, so grounding is traceable without changing the guardrail's grounding-check input (`check_facts` still reads `retrieved_chunks` text, unaffected).
- [x] Test: `tests/test_agent_nodes.py` — `retrieve()` populates `retrieved_sources` in the same order as `retrieved_chunks`.

## Phase 4: Hybrid retrieval (vector + in-process BM25, RRF fusion)

**Files:** `backend/app/agent/nodes.py`

- [x] Add `_bm25_scores(query, documents) -> list[float]`: minimal BM25 (k1=1.5, b=0.75, `re.findall(r"\w+", ...)` tokenizer), no new dependency.
  - `ponytail:` rebuilds the BM25 index from scratch every query — fine while the KB stays small (shop menu/policies); if the collection grows past a few thousand chunks, cache the index and invalidate on `embed_and_upsert`.
- [x] Add `_fuse_rrf(vector_scores, keyword_scores, k=60) -> list[str]`: ports `fuseWithRRF`'s rank-based formula (`1/(k+rank)` per source, summed, sorted desc) — no weighting knobs (no `RetrievalConfig` equivalent), k=60 fixed constant.
- [x] `retrieve()`: runs `coll.get()` + `_bm25_scores` alongside the existing vector query, fuses with `_fuse_rrf` before the existing rerank step when keyword hits exist (falls back to vector-only ordering otherwise). `score_threshold` stays vector-side only; RRF fusion happens after thresholding. Keyword search failures are caught and logged, degrading to vector-only rather than failing the turn.
- [x] Test: `tests/test_agent_nodes.py` — a keyword-only match surfaces in `retrieved_chunks` via hybrid fusion; `_bm25_scores`/`_fuse_rrf` unit tests.

## Verification

- Run `pytest backend/tests/` after each phase.
- Phase 2's migration: back up `backend/local.db` first (already two backup files present from prior work — follow that same naming pattern), run `alembic upgrade head`, verify `conversation_summaries.failed_attempts` column exists.
- No public API/contract changes — `retrieved_chunks` type is preserved; `retrieved_sources` and the new metric are additive.

## Risk score: Medium

Phase 4 is the highest-risk piece (new retrieval path affecting answer grounding) — test against real KB content before shipping, same way the existing `score_threshold=0.35` was tuned from observed data (see comment in `nodes.py:retrieve`).

## Out of scope (per decision matrix)

- WeKnora's heading/heuristic Go chunker tiers — doc-structure-specific, current bilingual LLM chunker already does semantic splitting.
- Full `modelcontext` resource-handle registry / MCP tool-policy machinery — no MCP surface in this bot.
- External keyword search service (Elasticsearch/Postgres FTS) — BM25 in-process is enough at this KB's size; upgrade path noted as a `ponytail:` comment in Phase 4.
