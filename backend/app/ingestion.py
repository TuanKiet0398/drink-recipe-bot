import json
import logging
import uuid

from pydantic import BaseModel

from app.retry import retry_once
from app.token_usage import log_token_usage

logger = logging.getLogger(__name__)

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


def split_into_pieces(text: str, max_chars: int = 12000) -> list[str]:
    """Pre-splits `text` on paragraph boundaries (`\\n\\n`) into pieces no
    longer than `max_chars`, so a very long document never gets sent as a
    single LLM chunking call. A single paragraph longer than `max_chars` is
    kept whole rather than cut mid-sentence."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        added_len = len(paragraph) + (2 if current else 0)
        if current and current_len + added_len > max_chars:
            pieces.append("\n\n".join(current))
            current = []
            current_len = 0
            added_len = len(paragraph)
        current.append(paragraph)
        current_len += added_len
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Naive word-count chunker — the fallback used when LLM chunking fails."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks or [text]


def _chunk_via_llm(
    text: str, filename: str, chat_client, chat_model: str, db, user_id: int | None
) -> list[Chunk]:
    def _call():
        return chat_client.chat.completions.create(
            model=chat_model,
            messages=[{"role": "user", "content": _CHUNK_PROMPT.format(filename=filename, text=text)}],
            response_format={"type": "json_object"},
        )

    response = retry_once(_call, call_type="chunk_document", model=chat_model)
    log_token_usage(db, user_id, "chunk_document", chat_model, response.usage)
    parsed = json.loads(response.choices[0].message.content)
    return [Chunk.model_validate(c) for c in parsed["chunks"]]


def chunk_document(
    text: str,
    filename: str,
    chat_client,
    chat_model: str,
    db,
    user_id: int | None = None,
    max_chars: int = 12000,
) -> list[Chunk]:
    """Split `text` into bilingual (Vietnamese/English headline+summary)
    chunks via an LLM call. Documents longer than `max_chars` are
    pre-split on paragraph boundaries (`split_into_pieces`) and chunked one
    piece at a time, so a long document never blows a single LLM call's
    context. Falls back to the naive `chunk_text()` splitter (wrapped as
    single-field chunks) if any piece's LLM call fails or returns
    unparseable output, so a provider outage never blocks a document
    upload."""
    try:
        chunks: list[Chunk] = []
        for piece in split_into_pieces(text, max_chars=max_chars):
            chunks.extend(_chunk_via_llm(piece, filename, chat_client, chat_model, db, user_id))
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
    embedding_client,
    collection: str = "matcha_knowledge",
) -> None:
    from app.agent.clients import get_or_create_collection

    coll = get_or_create_collection(chroma_client, collection)

    texts = [chunk.as_text() for chunk in chunks]
    embeddings = [
        embedding_client.embeddings.create(model=EMBEDDING_MODEL, input=text).data[0].embedding
        for text in texts
    ]
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"filename": filename, "document_id": document_id} for _ in chunks]

    coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
