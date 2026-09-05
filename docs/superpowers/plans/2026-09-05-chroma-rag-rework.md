# Chroma-based RAG Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Qdrant-backed RAG pipeline with an embedded ChromaDB pipeline that uses LLM-based bilingual (Vietnamese/English) semantic chunking on ingestion and query-rewrite + dual-retrieve + LLM-rerank on every chat turn, fixing the bug where Vietnamese-phrased questions return no recipes.

**Architecture:** `chromadb.PersistentClient` replaces `QdrantClient` as an in-process vector store (no separate service). Ingestion (`app/ingestion.py`) chunks documents via an OpenAI LLM call that produces bilingual headline/summary text per chunk, falling back to the existing naive word-count chunker on failure. Retrieval (`app/agent/nodes.py::retrieve`) rewrites the user's question with an LLM call, embeds and queries Chroma with both the original and rewritten question, merges unique hits by cosine score, and reranks the merged set with a third LLM call before handing the top chunks to the unchanged `generate()` step.

**Tech Stack:** Python 3.11, FastAPI, ChromaDB (`chromadb`, `PersistentClient`), OpenAI Python SDK (`gpt-4o-mini` for chunking/rewrite/rerank, `text-embedding-3-small` for embeddings), SQLAlchemy, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-chroma-rag-rework-design.md`

## Global Constraints

- No new LLM provider dependencies (no litellm, no Groq) — chunking/rewrite/rerank all use the existing OpenAI client.
- Query rewrite + rerank run on every chat turn (not gated behind a flag) — the user explicitly accepted the added latency/cost.
- ChromaDB runs embedded (`PersistentClient`), not as a separate service — no new Docker container.
- Chunking prompt must instruct the LLM to write `headline` and `summary` bilingually (Vietnamese + English); `original_text` stays unchanged in the source language.
- `score_threshold` moves from `0.35` to `0.20` (carried over unchanged in scale: Chroma's cosine `score = 1 - distance` matches Qdrant's cosine score semantics), and must still reject an off-topic query in the final smoke test (Task 8).
- Every new OpenAI call follows the existing `log_token_usage(db, user_id, call_type, model, usage)` convention already used in `app/agent/nodes.py`.
- Every new external call (LLM chunking, rewrite, rerank) must degrade gracefully per the spec's Error Handling section — never fail a user-facing upload or chat turn because of it.
- `backend/kb/` is deleted once its ideas are merged in (Task 8).

---

## Task 1: Dependencies and configuration

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py:30`
- Modify: `backend/.gitignore`
- Modify: `backend/.env`

**Interfaces:**
- Produces: `Settings.chroma_persist_dir: str` (default `"./chroma_db"`), consumed by Task 2's `get_chroma_client()`.

- [ ] **Step 1: Remove `qdrant-client`, add `chromadb` in `pyproject.toml`**

In `backend/pyproject.toml`, replace this line in `[project].dependencies`:

```toml
    "qdrant-client>=1.11",
```

with:

```toml
    "chromadb>=0.5",
```

- [ ] **Step 2: Install the updated dependencies**

Run: `cd backend && pip install -e .`
Expected: install succeeds, `chromadb` importable — verify with `python3 -c "import chromadb; print(chromadb.__version__)"`.

- [ ] **Step 3: Update `Settings` in `app/config.py`**

Replace the whole file with:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    chroma_persist_dir: str = "./chroma_db"
    telegram_bot_token: str = ""
    database_url: str = "sqlite:///./local.db"
    admin_username: str = "admin"
    admin_password: str = "admin"
    telegram_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Update the unsafe-defaults warning in `app/main.py`**

In `app/main.py`, change line 30 from:

```python
    if settings.admin_password == "admin" or settings.openai_api_key == "" or settings.qdrant_url == "":
```

to:

```python
    if settings.admin_password == "admin" or settings.openai_api_key == "":
```

- [ ] **Step 5: Update `.env` and `.gitignore`**

In `backend/.env`, remove the `QDRANT_URL=` and `QDRANT_API_KEY=` lines and add:

```
CHROMA_PERSIST_DIR=./chroma_db
```

In `backend/.gitignore`, add a line:

```
chroma_db/
```

- [ ] **Step 6: Verify the app still boots**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3 -m pytest -q`
Expected: existing suite still collects and runs (later tasks will fix the Qdrant-specific failures this introduces — for now, confirm there's no import-time crash from the config change, e.g. no `AttributeError: 'Settings' object has no attribute 'qdrant_url'` at collection time). It's OK if Qdrant-dependent tests now fail; they get fixed in Tasks 4-6.

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/pyproject.toml backend/app/config.py backend/app/main.py backend/.gitignore backend/.env
git commit -m "chore(backend): swap qdrant-client for chromadb dependency and config"
```

---

## Task 2: Chroma client module

**Files:**
- Modify: `backend/app/agent/clients.py`
- Test: `backend/tests/test_agent_clients.py` (new)

**Interfaces:**
- Consumes: `Settings.chroma_persist_dir` (Task 1).
- Produces: `get_chroma_client() -> chromadb.PersistentClient` and `get_or_create_collection(chroma_client, name: str = "matcha_knowledge")` — used by Task 3 (`app/ingestion.py`), Task 4 (`app/agent/nodes.py`), and Task 6 (`app/routers/admin_docs.py`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_clients.py`:

```python
from chromadb import PersistentClient

from app.agent.clients import get_or_create_collection


def test_get_or_create_collection_round_trips_a_real_upsert_and_query(tmp_path):
    # Real ChromaDB (no network calls — it's a local, file-backed store), to
    # catch API-usage mistakes that a fully-mocked test would miss.
    client = PersistentClient(path=str(tmp_path))

    collection = get_or_create_collection(client, "test_collection")
    collection.upsert(
        ids=["1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["hello world"],
        metadatas=[{"document_id": 42}],
    )

    result = collection.query(query_embeddings=[[1.0, 0.0, 0.0]], n_results=1)

    assert result["documents"][0] == ["hello world"]
    assert result["distances"][0][0] < 0.01  # identical vector -> ~0 cosine distance


def test_get_or_create_collection_is_idempotent(tmp_path):
    client = PersistentClient(path=str(tmp_path))

    first = get_or_create_collection(client, "test_collection")
    second = get_or_create_collection(client, "test_collection")

    assert first.name == second.name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_agent_clients.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_or_create_collection' from 'app.agent.clients'`.

- [ ] **Step 3: Rewrite `app/agent/clients.py`**

Replace the whole file with:

```python
from functools import lru_cache

from chromadb import PersistentClient
from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_agent_clients.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/agent/clients.py backend/tests/test_agent_clients.py
git commit -m "feat(backend): replace Qdrant client with embedded ChromaDB client"
```

---

## Task 3: Ingestion rework — bilingual LLM chunking + Chroma upsert

**Files:**
- Modify: `backend/app/ingestion.py`
- Test: `backend/tests/test_ingestion.py` (new)

**Interfaces:**
- Consumes: `get_or_create_collection(chroma_client, name)` (Task 2).
- Produces: `Chunk` (Pydantic model: `headline: str`, `summary: str`, `original_text: str`, method `as_text() -> str`), `chunk_document(text: str, filename: str, openai_client, db, user_id: int | None = None) -> list[Chunk]`, `embed_and_upsert(chunks: list[Chunk], filename: str, document_id: int, chroma_client, openai_client, collection: str = "matcha_knowledge") -> None`. Both consumed by Task 6 (`app/routers/admin_docs.py`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ingestion.py`:

```python
import json
from unittest.mock import MagicMock, patch

from chromadb import PersistentClient

from app.agent.clients import get_or_create_collection
from app.ingestion import Chunk, chunk_document, chunk_text, embed_and_upsert


def test_chunk_text_splits_into_word_count_windows():
    text = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_text(text, chunk_size=500)
    assert len(chunks) == 3
    assert chunks[0].split()[0] == "word0"


def test_chunk_text_returns_whole_text_when_shorter_than_chunk_size():
    assert chunk_text("just a few words") == ["just a few words"]


def test_chunk_document_parses_bilingual_llm_response_into_chunks(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "chunks": [
                            {
                                "headline": "Matcha Latte / Trà Sữa Matcha",
                                "summary": "How to make a matcha latte. / Cách pha trà sữa matcha.",
                                "original_text": "Whisk 2g matcha with steamed milk.",
                            }
                        ]
                    }
                )
            )
        )
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunks = chunk_document("Whisk 2g matcha with steamed milk.", "matcha-latte.txt", openai_client=fake_openai, db=db_session)

    assert len(chunks) == 1
    assert chunks[0].original_text == "Whisk 2g matcha with steamed milk."
    assert "Trà Sữa" in chunks[0].headline
    fake_openai.chat.completions.create.assert_called_once()
    assert fake_openai.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_chunk_document_prompt_asks_for_bilingual_headline_and_summary(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"chunks": [{"headline": "H", "summary": "S", "original_text": "T"}]})))
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunk_document("T", "doc.txt", openai_client=fake_openai, db=db_session)

    prompt = fake_openai.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Vietnamese" in prompt
    assert "English" in prompt


def test_chunk_document_falls_back_to_naive_chunking_when_llm_fails(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("provider down")

    with patch("app.retry.time.sleep"):
        chunks = chunk_document("word " * 10, "doc.txt", openai_client=fake_openai, db=db_session)

    assert len(chunks) == 1
    assert chunks[0].original_text.startswith("word")
    assert chunks[0].summary == ""


def test_chunk_document_falls_back_when_llm_response_is_malformed_json(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="not valid json"))
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunks = chunk_document("some document text", "doc.txt", openai_client=fake_openai, db=db_session)

    assert len(chunks) == 1
    assert chunks[0].original_text == "some document text"


def test_embed_and_upsert_writes_chunk_text_and_metadata_to_chroma():
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2])]
    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    chunk = Chunk(headline="H", summary="S", original_text="T")
    embed_and_upsert([chunk], filename="a.txt", document_id=42, chroma_client=fake_chroma, openai_client=fake_openai)

    fake_collection.upsert.assert_called_once()
    kwargs = fake_collection.upsert.call_args.kwargs
    assert kwargs["documents"] == ["H\n\nS\n\nT"]
    assert kwargs["metadatas"] == [{"filename": "a.txt", "document_id": 42}]
    assert len(kwargs["ids"]) == 1


def test_embed_and_upsert_round_trips_through_real_chroma(tmp_path):
    # One non-mocked test against a real (local, file-backed) Chroma
    # instance, so a Chroma API mistake (wrong kwarg name, wrong return
    # shape) fails here instead of only in fully-mocked unit tests.
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[1.0, 0.0])]
    real_chroma = PersistentClient(path=str(tmp_path))

    chunk = Chunk(headline="Matcha Latte", summary="A latte.", original_text="Whisk matcha with milk.")
    embed_and_upsert([chunk], filename="matcha.txt", document_id=1, chroma_client=real_chroma, openai_client=fake_openai)

    collection = get_or_create_collection(real_chroma, "matcha_knowledge")
    result = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)
    assert "Whisk matcha with milk." in result["documents"][0][0]
    assert result["metadatas"][0][0]["document_id"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_ingestion.py -v`
Expected: FAIL — `chunk_document` doesn't exist yet, `embed_and_upsert` has the old Qdrant-based signature.

- [ ] **Step 3: Rewrite `app/ingestion.py`**

Replace the whole file with:

```python
import json
import logging
import uuid

from pydantic import BaseModel

from app.retry import retry_once
from app.token_usage import log_token_usage

logger = logging.getLogger(__name__)

CHUNK_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

_CHUNK_PROMPT = """You split a document into overlapping chunks for a shop's knowledge base chatbot.

The chatbot's customers ask questions in Vietnamese; this document is written in English. For EACH chunk, write the "headline" and "summary" fields bilingually: include both a Vietnamese and an English phrasing, so a Vietnamese-language question can match this chunk by embedding similarity. The "original_text" field must stay in the document's original language and wording, unchanged.

Split the document so its entire content is covered across chunks, with roughly 25% overlap between adjacent chunks.

Respond with strict JSON: {{"chunks": [{{"headline": "...", "summary": "...", "original_text": "..."}}, ...]}}

Document (filename: {filename}):

{text}
"""


class Chunk(BaseModel):
    headline: str
    summary: str
    original_text: str

    def as_text(self) -> str:
        return f"{self.headline}\n\n{self.summary}\n\n{self.original_text}"


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Naive word-count chunker — the fallback used when LLM chunking fails."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks or [text]


def _chunk_via_llm(text: str, filename: str, openai_client, db, user_id: int | None) -> list[Chunk]:
    def _call():
        return openai_client.chat.completions.create(
            model=CHUNK_MODEL,
            messages=[{"role": "user", "content": _CHUNK_PROMPT.format(filename=filename, text=text)}],
            response_format={"type": "json_object"},
        )

    response = retry_once(_call)
    log_token_usage(db, user_id, "chunk_document", CHUNK_MODEL, response.usage)
    parsed = json.loads(response.choices[0].message.content)
    return [Chunk.model_validate(c) for c in parsed["chunks"]]


def chunk_document(text: str, filename: str, openai_client, db, user_id: int | None = None) -> list[Chunk]:
    """Split `text` into bilingual (Vietnamese/English headline+summary)
    chunks via an LLM call. Falls back to the naive `chunk_text()` splitter
    (wrapped as single-field chunks) if the LLM call fails or returns
    unparseable output, so a provider outage never blocks a document upload.
    """
    try:
        chunks = _chunk_via_llm(text, filename, openai_client, db, user_id)
        if chunks:
            return chunks
    except Exception:
        logger.exception("LLM chunking failed for %s; falling back to naive chunking", filename)
    return [Chunk(headline=filename, summary="", original_text=piece) for piece in chunk_text(text)]


def embed_and_upsert(
    chunks: list[Chunk],
    filename: str,
    document_id: int,
    chroma_client,
    openai_client,
    collection: str = "matcha_knowledge",
) -> None:
    from app.agent.clients import get_or_create_collection

    coll = get_or_create_collection(chroma_client, collection)

    texts = [chunk.as_text() for chunk in chunks]
    embeddings = [
        openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text).data[0].embedding
        for text in texts
    ]
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"filename": filename, "document_id": document_id} for _ in chunks]

    coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_ingestion.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/ingestion.py backend/tests/test_ingestion.py
git commit -m "feat(backend): bilingual LLM chunking + Chroma upsert in ingestion"
```

---

## Task 4: Retrieval rework — query rewrite, dual retrieve, rerank

**Files:**
- Modify: `backend/app/agent/nodes.py:1-79` (imports and `retrieve()`; `_build_system_prompt`, `generate`, `extract_favourite` at lines 82-169 are unchanged)
- Modify: `backend/tests/test_agent_nodes.py` (replace the six `test_retrieve_*` tests)

**Interfaces:**
- Consumes: `get_or_create_collection(chroma_client, name)` (Task 2).
- Produces: `retrieve(state, db, chroma_client, openai_client, collection="matcha_knowledge", retrieval_k=10, final_k=5, score_threshold=0.20) -> AgentState` (param renamed from `qdrant_client`; consumed by Task 5's `graph.py`), `rewrite_query(question: str, history: list[dict], openai_client, db, user_id: int | None) -> str`, `rerank(question: str, chunks: list[str], openai_client, db, user_id: int | None) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_agent_nodes.py`, add `import json` to the top of the file (alongside the existing `datetime`/`unittest.mock` imports), then replace the six existing tests named `test_retrieve_queries_qdrant_and_fills_chunks`, `test_retrieve_returns_no_chunks_when_qdrant_filters_everything_below_threshold`, `test_retrieve_creates_collection_when_missing`, `test_retrieve_tolerates_search_failure_and_returns_empty_chunks`, and `test_retrieve_retries_openai_embedding_once_then_succeeds` with:

```python
def _fake_chroma(query_results):
    """query_results: a list of {"documents": [[...]], "distances": [[...]]}
    dicts, consumed in order by successive collection.query() calls."""
    fake_collection = MagicMock()
    fake_collection.query.side_effect = query_results
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    return fake_chroma, fake_collection


def _fake_openai_with_rewrite(embedding=None, rewritten_text=None):
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=embedding or [0.1, 0.2, 0.3])]
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=rewritten_text or "how to brew matcha?"))
    ]
    fake_openai.chat.completions.create.return_value.usage = None
    return fake_openai


def test_retrieve_returns_top_chunk_above_threshold(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_chroma, fake_collection = _fake_chroma(
        [{"documents": [["Whisk matcha with a bamboo chasen."]], "distances": [[0.1]]}]
    )

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == ["Whisk matcha with a bamboo chasen."]
    # The rewritten query is identical to the original, so only one
    # embed+query round trip happens (no redundant second search).
    fake_collection.query.assert_called_once()


def test_retrieve_filters_out_hits_below_score_threshold(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how do I brew coffee?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how do I brew coffee?")
    # distance=0.9 -> score=0.1, below the 0.20 default threshold
    fake_chroma, _ = _fake_chroma([{"documents": [["irrelevant tea chunk"]], "distances": [[0.9]]}])

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_searches_twice_and_merges_when_rewrite_differs(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="cách pha trà xanh")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew green tea")
    fake_openai.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="how to brew green tea"))], usage=None),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"order": [2, 1]})))], usage=None),
    ]
    fake_chroma, fake_collection = _fake_chroma(
        [
            {"documents": [["Chunk A"]], "distances": [[0.2]]},
            {"documents": [["Chunk B"]], "distances": [[0.1]]},
        ]
    )

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert fake_collection.query.call_count == 2
    # Merged order by score would be [Chunk B (0.9), Chunk A (0.8)];
    # rerank's order=[2, 1] flips that to [Chunk A, Chunk B].
    assert result.retrieved_chunks == ["Chunk A", "Chunk B"]


def test_retrieve_tolerates_chroma_query_failure_and_returns_empty_chunks(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_collection = MagicMock()
    fake_collection.query.side_effect = RuntimeError("collection not found")
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_retries_openai_embedding_once_then_succeeds(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_openai.embeddings.create.side_effect = [
        RuntimeError("transient"),
        MagicMock(data=[MagicMock(embedding=[0.1, 0.2, 0.3])]),
    ]
    fake_chroma, _ = _fake_chroma([{"documents": [[]], "distances": [[]]}])

    with patch("app.retry.time.sleep"):
        result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert fake_openai.embeddings.create.call_count == 2
    assert result.retrieved_chunks == []


def test_rewrite_query_falls_back_to_original_question_when_llm_fails():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("down")

    with patch("app.retry.time.sleep"):
        result = rewrite_query("how to brew matcha?", [], fake_openai, db=MagicMock(), user_id=1)

    assert result == "how to brew matcha?"


def test_rerank_reorders_chunks_by_llm_response():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"order": [2, 1]})))
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    result = rerank("q", ["first", "second"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["second", "first"]


def test_rerank_keeps_original_order_when_llm_response_is_incomplete():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"order": [1]})))  # missing chunk 2
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    result = rerank("q", ["first", "second"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["first", "second"]


def test_rerank_skips_llm_call_for_a_single_chunk():
    fake_openai = MagicMock()

    result = rerank("q", ["only chunk"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["only chunk"]
    fake_openai.chat.completions.create.assert_not_called()
```

Update the import line at the top of `tests/test_agent_nodes.py` from:

```python
from app.agent.nodes import fetch_history, retrieve, generate, extract_favourite
```

to:

```python
from app.agent.nodes import fetch_history, retrieve, rerank, rewrite_query, generate, extract_favourite
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_agent_nodes.py -v`
Expected: FAIL — `rerank`/`rewrite_query` don't exist yet, `retrieve()` still takes `qdrant_client`.

- [ ] **Step 3: Rewrite `retrieve()` and add `rewrite_query()`/`rerank()` in `app/agent/nodes.py`**

Replace lines 1-79 (everything from the top of the file through the end of the current `retrieve()` function) with:

```python
import json
import logging
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.clients import get_or_create_collection
from app.agent.state import AgentState
from app.db.models import Favourite, Message
from app.retry import retry_once
from app.token_usage import log_token_usage

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
REWRITE_MODEL = "gpt-4o-mini"
RERANK_MODEL = "gpt-4o-mini"


def fetch_history(state: AgentState, db: Session, limit: int = 10) -> AgentState:
    rows = (
        db.execute(
            select(Message)
            .where(Message.user_id == state.user_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    rows = list(reversed(rows))
    state.history = [{"role": m.role, "content": m.content} for m in rows]

    favourite_rows = (
        db.execute(select(Favourite).where(Favourite.user_id == state.user_id))
        .scalars()
        .all()
    )
    state.favourites = [f.drink_name for f in favourite_rows]
    return state


def rewrite_query(question: str, history: list[dict], openai_client, db: Session, user_id: int | None) -> str:
    """Condenses the conversation + question into a focused knowledge-base
    search query. Falls back to the original question if the LLM call
    fails, so retrieval degrades to a single (still-valid) search rather
    than failing the chat turn."""
    prompt = (
        "You are about to search a knowledge base to answer the user's question.\n"
        f"Conversation so far: {history}\n"
        f"User's current question: {question}\n\n"
        "Condense this into a single short, specific search query most likely "
        "to surface relevant content, folding in any needed context from the "
        "conversation. Respond ONLY with the query text, nothing else."
    )

    def _call():
        return openai_client.chat.completions.create(
            model=REWRITE_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        response = retry_once(_call)
    except Exception:
        logger.exception("rewrite_query failed; falling back to the original question")
        return question

    log_token_usage(db, user_id, "rewrite_query", REWRITE_MODEL, response.usage)
    rewritten = (response.choices[0].message.content or "").strip()
    return rewritten or question


def rerank(question: str, chunks: list[str], openai_client, db: Session, user_id: int | None) -> list[str]:
    """Reorders `chunks` by relevance to `question` via an LLM call. Falls
    back to the original (retrieval-score) order if the call fails or
    returns an incomplete ranking."""
    if len(chunks) <= 1:
        return chunks

    numbered = "\n\n".join(f"# CHUNK {i + 1}:\n{chunk}" for i, chunk in enumerate(chunks))
    prompt = (
        f"The user asked: {question}\n\n"
        "Rank the following chunks by relevance to the question, most "
        'relevant first. Respond with strict JSON: {"order": [chunk numbers, '
        "most relevant first]}, including every chunk number exactly once.\n\n"
        f"{numbered}"
    )

    def _call():
        return openai_client.chat.completions.create(
            model=RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

    try:
        response = retry_once(_call)
        log_token_usage(db, user_id, "rerank", RERANK_MODEL, response.usage)
        order = json.loads(response.choices[0].message.content)["order"]
        reranked = [chunks[i - 1] for i in order if 1 <= i <= len(chunks)]
        if len(reranked) == len(chunks):
            return reranked
    except Exception:
        logger.exception("rerank failed; keeping retrieval order")
    return chunks


def retrieve(
    state: AgentState,
    db: Session,
    chroma_client,
    openai_client,
    collection: str = "matcha_knowledge",
    retrieval_k: int = 10,
    final_k: int = 5,
    score_threshold: float = 0.20,
) -> AgentState:
    def _embed(text: str) -> list[float]:
        response = retry_once(
            lambda: openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        )
        log_token_usage(db, state.user_id, "embedding", EMBEDDING_MODEL, response.usage)
        return response.data[0].embedding

    try:
        coll = get_or_create_collection(chroma_client, collection)

        rewritten = rewrite_query(state.incoming_text, state.history, openai_client, db, state.user_id)
        query_texts = [state.incoming_text]
        if rewritten != state.incoming_text:
            query_texts.append(rewritten)

        best_scores: dict[str, float] = {}
        for query_text in query_texts:
            embedding = _embed(query_text)
            result = coll.query(query_embeddings=[embedding], n_results=retrieval_k)
            texts = result["documents"][0] if result["documents"] else []
            distances = result["distances"][0] if result["distances"] else []
            for text, distance in zip(texts, distances):
                score = 1 - distance
                if score >= score_threshold:
                    best_scores[text] = max(best_scores.get(text, score), score)
    except Exception:
        # Tolerate a not-yet-existing (or otherwise unreachable) collection:
        # fall back to no retrieved context rather than failing the whole
        # agent turn.
        logger.exception("retrieval failed for user_id=%s", state.user_id)
        state.retrieved_chunks = []
        return state

    merged = sorted(best_scores, key=best_scores.get, reverse=True)
    state.retrieved_chunks = rerank(state.incoming_text, merged, openai_client, db, state.user_id)[:final_k]
    return state
```

Leave `_build_system_prompt`, `generate`, and `extract_favourite` (currently lines 82-169) exactly as they are.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_agent_nodes.py -v`
Expected: PASS (all tests in the file, including the unmodified `generate`/`extract_favourite` tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/agent/nodes.py backend/tests/test_agent_nodes.py
git commit -m "feat(backend): rewrite+dual-retrieve+rerank against Chroma in retrieve()"
```

---

## Task 5: Wire Chroma through the agent graph and webhook

**Files:**
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/routers/webhook.py:8,173,186`
- Modify: `backend/tests/test_agent_graph.py`
- Modify: `backend/tests/test_webhook.py:16-27,53-61`

**Interfaces:**
- Consumes: `retrieve(state, db, chroma_client, openai_client, ...)` (Task 4), `get_chroma_client()` (Task 2).
- Produces: `run_agent(state, db, chroma_client, openai_client, on_delta=None) -> AgentState` (param renamed from `qdrant_client`).

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_agent_graph.py`, replace the whole file with:

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

    stream_chunk = MagicMock()
    stream_chunk.choices = [MagicMock(delta=MagicMock(content="Try ceremonial grade!"))]
    stream_chunk.usage = None
    final_chunk = MagicMock()
    final_chunk.choices = []
    final_chunk.usage = None
    fake_openai.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="recommend a matcha"))], usage=None),  # rewrite_query
        [stream_chunk, final_chunk],  # generate()'s stream
    ]

    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [[]], "distances": [[]]}
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    seen: list[str] = []
    result = run_agent(state, db=db_session, chroma_client=fake_chroma, openai_client=fake_openai, on_delta=seen.append)

    assert result.reply == "Try ceremonial grade!"
    assert seen == ["Try ceremonial grade!"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_agent_graph.py -v`
Expected: FAIL with `TypeError: run_agent() got an unexpected keyword argument 'chroma_client'`.

- [ ] **Step 3: Rename the parameter in `app/agent/graph.py`**

Replace the whole file with:

```python
from typing import Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import fetch_history, generate, retrieve
from app.agent.state import AgentState


def build_graph(db: Session, chroma_client, openai_client, on_delta: Callable[[str], None] | None = None):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", lambda s: fetch_history(s, db))
    graph.add_node("retrieve", lambda s: retrieve(s, db, chroma_client, openai_client))
    graph.add_node("generate", lambda s: generate(s, db, openai_client, on_delta=on_delta))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(
    state: AgentState,
    db: Session,
    chroma_client,
    openai_client,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    compiled = build_graph(db, chroma_client, openai_client, on_delta=on_delta)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
```

- [ ] **Step 4: Update `app/routers/webhook.py`**

Change line 8 from:

```python
from app.agent.clients import get_openai_client, get_qdrant_client
```

to:

```python
from app.agent.clients import get_chroma_client, get_openai_client
```

Change the comment at line 173 (previously referencing `get_qdrant_client()/get_openai_client()`) and the call site at line 186 from:

```python
            qdrant_client=get_qdrant_client(),
```

to:

```python
            chroma_client=get_chroma_client(),
```

- [ ] **Step 5: Update `tests/test_webhook.py` patches**

In `tests/test_webhook.py`, replace every occurrence of `"app.routers.webhook.get_qdrant_client"` with `"app.routers.webhook.get_chroma_client"` (two occurrences, in `test_webhook_creates_user_stores_message_and_replies` and `test_webhook_delivers_streamed_reply_progressively`). The `run_agent` mock in these tests is on `app.routers.webhook.run_agent` itself, so no further changes are needed there.

- [ ] **Step 6: Run both test files to verify they pass**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3 -m pytest tests/test_agent_graph.py tests/test_webhook.py -v`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/agent/graph.py backend/app/routers/webhook.py backend/tests/test_agent_graph.py backend/tests/test_webhook.py
git commit -m "refactor(backend): thread chroma_client through the agent graph and webhook"
```

---

## Task 6: Admin document upload/delete against Chroma

**Files:**
- Modify: `backend/app/routers/admin_docs.py`
- Modify: `backend/tests/test_admin_docs.py`

**Interfaces:**
- Consumes: `chunk_document`, `embed_and_upsert` (Task 3), `get_chroma_client`, `get_or_create_collection` (Task 2).

- [ ] **Step 1: Write the failing tests**

Replace the whole `backend/tests/test_admin_docs.py` with:

```python
from io import BytesIO
from unittest.mock import MagicMock, patch

from app.db.models import AdminAuditLog, Document
from app.ingestion import Chunk


def test_upload_doc_requires_auth(client):
    response = client.post("/admin/docs", files={"file": ("brew.txt", BytesIO(b"steep 80C"))})
    assert response.status_code == 401


def test_upload_doc_chunks_embeds_and_records_metadata(client, db_session):
    fake_chunks = [Chunk(headline="H", summary="S", original_text="Steep sencha at 70C for 60 seconds.")]

    with patch("app.routers.admin_docs.chunk_document", return_value=fake_chunks) as mock_chunk, patch(
        "app.routers.admin_docs.embed_and_upsert"
    ) as mock_embed:
        response = client.post(
            "/admin/docs",
            files={"file": ("sencha_recipe.txt", BytesIO(b"Steep sencha at 70C for 60 seconds."))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sencha_recipe.txt"
    assert body["chunk_count"] == 1
    assert db_session.query(Document).count() == 1
    mock_chunk.assert_called_once()
    mock_embed.assert_called_once()
    assert mock_embed.call_args.kwargs["chunks"] == fake_chunks
    assert mock_embed.call_args.kwargs["document_id"] == body["id"]


def test_upload_doc_rejects_pdf_extension(client, db_session):
    response = client.post(
        "/admin/docs",
        files={"file": ("brew.pdf", BytesIO(b"%PDF-1.4 fake pdf bytes"))},
        auth=("admin", "admin"),
    )
    assert response.status_code == 400
    assert "Only .txt and .md files" in response.json()["detail"]
    assert db_session.query(Document).count() == 0


def test_upload_doc_rejects_oversized_file(client, db_session):
    big_content = b"a" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/admin/docs",
        files={"file": ("big.txt", BytesIO(big_content))},
        auth=("admin", "admin"),
    )
    assert response.status_code == 413
    assert db_session.query(Document).count() == 0


def test_upload_doc_accepts_md_file(client, db_session):
    with patch("app.routers.admin_docs.chunk_document", return_value=[Chunk(headline="H", summary="S", original_text="# Matcha notes")]), patch(
        "app.routers.admin_docs.embed_and_upsert"
    ):
        response = client.post(
            "/admin/docs",
            files={"file": ("notes.md", BytesIO(b"# Matcha notes"))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
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

    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    with patch("app.routers.admin_docs.get_chroma_client", return_value=fake_chroma):
        response = client.delete(f"/admin/docs/{doc.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Document).count() == 0
    fake_collection.delete.assert_called_once_with(where={"document_id": doc.id})


def test_delete_doc_with_duplicate_filename_only_deletes_its_own_document_id(client, db_session):
    from app.db.models import Document as DocumentModel

    doc1 = DocumentModel(filename="dup.txt", chunk_count=1)
    doc2 = DocumentModel(filename="dup.txt", chunk_count=1)
    db_session.add_all([doc1, doc2])
    db_session.commit()
    db_session.refresh(doc1)
    db_session.refresh(doc2)

    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    with patch("app.routers.admin_docs.get_chroma_client", return_value=fake_chroma):
        response = client.delete(f"/admin/docs/{doc1.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    fake_collection.delete.assert_called_once_with(where={"document_id": doc1.id})
    assert db_session.query(DocumentModel).filter_by(id=doc2.id).count() == 1


def test_delete_doc_returns_404_when_missing(client, db_session):
    response = client.delete("/admin/docs/999", auth=("admin", "admin"))
    assert response.status_code == 404


def test_upload_doc_writes_audit_log(client, db_session):
    with patch("app.routers.admin_docs.chunk_document", return_value=[Chunk(headline="H", summary="S", original_text="content")]), patch(
        "app.routers.admin_docs.embed_and_upsert"
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

Note: the old `test_upload_doc_creates_qdrant_collection_when_missing` and `test_upload_doc_stores_document_id_in_qdrant_payload` tests are removed — collection creation is now `get_or_create_collection`'s concern (covered by `test_agent_clients.py` in Task 2) and `document_id` propagation into `embed_and_upsert` is covered by the new `mock_embed.call_args.kwargs["document_id"]` assertion above. `test_delete_doc_returns_404_when_missing` is a new test filling a gap the old suite didn't cover.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_admin_docs.py -v`
Expected: FAIL — `app.routers.admin_docs.chunk_document` doesn't exist as an importable name there yet (still imports `chunk_text`/`embed_and_upsert` with the old signature), and `get_chroma_client` isn't imported in that module.

- [ ] **Step 3: Rewrite `app/routers/admin_docs.py`**

Replace the whole file with:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.agent.clients import get_chroma_client, get_openai_client, get_or_create_collection
from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Document
from app.ingestion import chunk_document, embed_and_upsert

router = APIRouter(prefix="/admin/docs")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = (".txt", ".md")


@router.post("", status_code=201)
async def upload_doc(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported currently",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 5MB upload limit")

    text = raw.decode("utf-8", errors="ignore")
    openai_client = get_openai_client()
    chunks = chunk_document(text, filename, openai_client=openai_client, db=db)

    doc = Document(filename=filename, chunk_count=len(chunks))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    embed_and_upsert(
        chunks=chunks,
        filename=filename,
        document_id=doc.id,
        chroma_client=get_chroma_client(),
        openai_client=openai_client,
    )

    log_admin_action(db, action="upload_doc", target=filename, ip=request.client.host if request.client else "")

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

    collection = get_or_create_collection(get_chroma_client(), "matcha_knowledge")
    collection.delete(where={"document_id": doc.id})

    db.delete(doc)
    db.commit()

    log_admin_action(db, action="delete_doc", target=doc.filename, ip=request.client.host if request.client else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3 -m pytest tests/test_admin_docs.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add backend/app/routers/admin_docs.py backend/tests/test_admin_docs.py
git commit -m "refactor(backend): admin doc upload/delete against Chroma"
```

---

## Task 7: Delete backend/kb/, remove the Qdrant container, full-suite verification

**Files:**
- Delete: `backend/kb/ingest.py`, `backend/kb/answer.py` (and the `backend/kb/` directory)

- [ ] **Step 1: Delete the prototype folder**

```bash
cd /mnt/d/Workspace/MLOPS_project
git rm -r backend/kb
```

- [ ] **Step 2: Run the full backend test suite**

Run: `cd backend && TELEGRAM_WEBHOOK_SECRET= python3 -m pytest -q`
Expected: all tests pass (no `qdrant` references remain anywhere — verify with `grep -rn qdrant backend/app backend/tests backend/pyproject.toml`, which should return nothing).

- [ ] **Step 3: Stop the now-unused Qdrant container**

Run: `docker stop dreamy_meitner` (the Qdrant container observed running on port 6333 during the investigation that motivated this rework). Confirm the backend still starts and serves without it — restart uvicorn and hit `/docs`.

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/Workspace/MLOPS_project
git add -A
git commit -m "chore(backend): remove kb/ prototype now that its ideas are merged"
```

---

## Task 8: Re-ingest existing documents and verify the original bug is fixed

**Files:** none (operational verification only — this task produces no code diff).

- [ ] **Step 1: Restart the backend with the new pipeline**

Kill any running `uvicorn app.main:app` process and restart it (see the running-instructions already established in this project: `python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/`). Confirm `backend/chroma_db/` gets created on first request.

- [ ] **Step 2: Re-upload the two existing recipe documents**

The two documents previously ingested into Qdrant (`/mnt/d/Workspace/MLOPS_project/sample-recipes/matcha-latte.txt` and `/mnt/d/Workspace/MLOPS_project/sample-recipes/honey-jasmine-green-tea.txt` — at the repo root, not under `backend/`) need to go through the new `/admin/docs` upload endpoint, since Task 7 stopped the old Qdrant instance and this pipeline never migrated its data automatically (by design — see the spec's "Out of scope" section).

```bash
curl -u admin:admin -F "file=@/mnt/d/Workspace/MLOPS_project/sample-recipes/matcha-latte.txt" http://127.0.0.1:8000/admin/docs
curl -u admin:admin -F "file=@/mnt/d/Workspace/MLOPS_project/sample-recipes/honey-jasmine-green-tea.txt" http://127.0.0.1:8000/admin/docs
```

Expected: both return `201` with a `chunk_count >= 1`.

- [ ] **Step 3: Verify the original bug is fixed with a direct retrieval check**

Run a short one-off script to call `retrieve()` directly against the live Chroma + OpenAI setup with the exact Vietnamese queries that returned zero hits during the original investigation:

```python
# backend/scripts/verify_retrieval.py (temporary — delete after running)
from app.agent.clients import get_chroma_client, get_openai_client
from app.agent.state import AgentState
from app.agent.nodes import retrieve
from app.db.base import SessionLocal

db = SessionLocal()
for query in ["cách pha trà xanh", "công thức trà xanh mật ong", "cà phê đen"]:
    state = AgentState(user_id=1, chat_id="1", incoming_text=query)
    result = retrieve(state, db, get_chroma_client(), get_openai_client())
    print(query, "->", len(result.retrieved_chunks), "chunk(s)")
db.close()
```

Run: `cd backend && python3 scripts/verify_retrieval.py`

Expected: `"cách pha trà xanh"` and `"công thức trà xanh mật ong"` (both previously returning 0 hits) now return >= 1 chunk each; `"cà phê đen"` (off-topic — the shop sells no coffee) still returns 0 chunks, confirming `score_threshold=0.20` still filters unrelated topics per the Global Constraints. If the off-topic query starts returning hits, raise `score_threshold` slightly and re-run before proceeding.

Delete the script once verified: `rm backend/scripts/verify_retrieval.py`.

- [ ] **Step 4: Manual end-to-end smoke test via Telegram**

Send a Vietnamese recipe question to the live bot (e.g. "cách pha trà xanh mật ong") and confirm it now returns an actual recipe instead of "shop doesn't have that."

- [ ] **Step 5: Commit** (only if Step 3's script left any tracked-file changes, e.g. an adjusted `score_threshold`)

```bash
cd /mnt/d/Workspace/MLOPS_project
git status
# If app/agent/nodes.py's score_threshold was adjusted in Step 3:
git add backend/app/agent/nodes.py
git commit -m "tune(backend): adjust score_threshold after live retrieval verification"
```
