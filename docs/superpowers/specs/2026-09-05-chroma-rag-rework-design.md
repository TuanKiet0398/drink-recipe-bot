# Chroma-based RAG rework (ingestion + retrieval)

## Problem

Two related problems in the current Qdrant-backed RAG pipeline:

1. Retrieval returns nothing for Vietnamese-phrased questions even when a
   relevant English-authored recipe document exists. Root cause (confirmed
   live): `score_threshold=0.35` in `retrieve()` (`app/agent/nodes.py:47`)
   cuts off legitimate cross-lingual matches, which score 0.26-0.33 for
   natural Vietnamese phrasing vs 0.67-0.70 for English phrasing of the same
   question.
2. Ingestion chunking is naive (`chunk_text()` in `app/ingestion.py:6`,
   fixed 500-word windows with no semantic boundary awareness or overlap),
   which produces low-quality, context-poor chunks that hurt retrieval
   regardless of threshold.

The user prototyped an alternative approach in `backend/kb/` (`ingest.py`,
`answer.py`) using ChromaDB + LLM-based semantic chunking + query
rewrite/rerank. This spec adapts those ideas into the main backend
(`app/`), replacing Qdrant, then deletes `backend/kb/`.

## Decisions locked in with the user

- **Vector store**: ChromaDB (`PersistentClient`), embedded directly in the
  backend process. No separate service — the running Qdrant Docker
  container (`dreamy_meitner`) is no longer needed once this ships.
- **Chunking LLM**: existing OpenAI client (`gpt-4o-mini`), not
  litellm/Groq as in the `kb/` prototype — avoids new provider dependencies.
- **Query rewrite + rerank**: applied on every chat turn (not skipped for
  latency/cost), per user's explicit choice.
- **`backend/kb/`**: deleted once its ideas are merged into `app/`.

## Architecture

```
Upload flow:
  admin uploads .txt/.md
    -> chunk_document(text) [OpenAI LLM, structured JSON: headline+summary+original_text per chunk]
       (falls back to naive chunk_text() if the LLM call fails after retry)
    -> embed each chunk (OpenAI text-embedding-3-small)
    -> chroma_client upsert into collection "matcha_knowledge"
       (metadata: filename, document_id)

Chat flow (per Telegram message):
  fetch_history (unchanged)
    -> retrieve():
         rewrite_query(question, history) [OpenAI LLM, retry_once, fallback: use original question]
         embed(original question) + embed(rewritten question)
         chroma.query() x2 (top RETRIEVAL_K each)
         merge unique chunks (by text)
         rerank(question, merged) [OpenAI LLM ranks chunk ids, retry_once, fallback: keep retrieval order]
         take top FINAL_K -> state.retrieved_chunks
    -> generate() (unchanged system-prompt assembly, consumes state.retrieved_chunks same as today)
```

Chroma data persists at `backend/chroma_db/` (added to `.gitignore`).

### Fixing the original cross-lingual bug

The chunking prompt explicitly instructs the LLM to write each chunk's
`headline` and `summary` **bilingually (Vietnamese + English)**, since real
users ask in Vietnamese but source documents are English. This directly
targets the root cause found during investigation (cross-lingual cosine
similarity is inherently lower) by putting Vietnamese vocabulary into the
embedded text itself, rather than only lowering the score threshold (which this rework carries
forward as a secondary safety net, tuned down from 0.35 to 0.20 — low
enough to pass the 0.26-0.33 cross-lingual matches confirmed during
investigation, while implementation re-verifies it still rejects an
off-topic query like "cà phê đen" before shipping).

## Components touched

| File | Change |
|---|---|
| `app/agent/clients.py` | Remove `get_qdrant_client`/`ensure_collection` (Qdrant-specific). Add `get_chroma_client()` (`lru_cache`, `PersistentClient(path=settings.chroma_persist_dir)`) and `get_or_create_collection(client, name)`. |
| `app/ingestion.py` | Replace `chunk_text()` naive splitter with `chunk_document(text, filename, doc_type) -> list[Chunk]` (LLM call + Pydantic parse, same `json_object` pattern as `extract_favourite` in `nodes.py`, no litellm). Keep `chunk_text()` as the fallback path. Rework `embed_and_upsert()` to target Chroma. |
| `app/agent/nodes.py` | `retrieve()` reworked per Chat flow above. Add `rewrite_query()` and `rerank()` helpers (module-level functions, OpenAI-backed, `retry_once`-wrapped with graceful fallback). `score_threshold` default lowered (final value TBD during implementation, re-tested against the live data). |
| `app/routers/admin_docs.py` | Swap `qdrant_client` for `chroma_client` throughout; `delete_doc` uses Chroma's metadata `where={"document_id": doc_id}` filter instead of Qdrant's `Filter`/`FieldCondition`. |
| `app/agent/graph.py`, `app/routers/webhook.py`, `app/telegram_poller.py` (any call site threading `qdrant_client` through) | Rename param/plumbing to `chroma_client`. |
| `app/config.py` | Remove `qdrant_url`/`qdrant_api_key`. Add `chroma_persist_dir: str = "./chroma_db"`. |
| `pyproject.toml` | Remove `qdrant-client`, add `chromadb`. |
| `backend/kb/` | Deleted once the above lands. |

## Error handling

- Chunking LLM failure (after `retry_once`): fall back to naive
  `chunk_text()` rather than failing the upload outright.
- `rewrite_query` failure: use the original question text as the "rewritten"
  query too (second retrieval becomes a harmless duplicate, deduped by the
  merge step).
- `rerank` failure: keep the merged chunks in their original
  (retrieval-order) sequence instead of failing the chat turn.
- Missing/empty Chroma collection: unchanged behavior — return no chunks,
  same as today's Qdrant tolerance.

These mirror the existing philosophy in this codebase (never fail a
user-facing chat turn or upload because of a non-critical enhancement
failing) — see the existing try/except tolerance in `retrieve()` and the
webhook's blanket exception handling.

## Testing

- Update existing tests that currently mock `qdrant_client` to mock
  `chroma_client` instead: `tests/test_admin_docs.py`,
  `tests/test_agent_nodes.py`, `tests/test_agent_graph.py`,
  `tests/test_webhook.py`.
- New unit tests:
  - `chunk_document()` parses a structured LLM response into `Chunk`
    objects with headline/summary/original_text.
  - `chunk_document()` falls back to `chunk_text()` when the LLM call
    raises.
  - `retrieve()` calls rewrite → dual query → merge → rerank in order and
    assembles `state.retrieved_chunks` from the top `FINAL_K`.
  - `rewrite_query()` / `rerank()` failure paths degrade gracefully (assert
    the chat turn still completes with a reply).
  - `embed_and_upsert()` upserts into Chroma with the expected
    `document_id`/`filename` metadata; `delete_doc` removes by that
    metadata filter.

## Out of scope

- Migrating currently-ingested Qdrant data — the 2 existing recipe
  documents get re-uploaded through the admin endpoint under the new
  pipeline (small enough to not need an automated migration script).
- Multiprocessing chunking (`kb/ingest.py`'s `Pool`/`WORKERS`) — the admin
  upload endpoint processes one file at a time already; no parallelism
  needed.
- Any change to `generate()`'s system-prompt assembly — it keeps consuming
  `state.retrieved_chunks` exactly as it does today.
