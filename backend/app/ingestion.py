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
