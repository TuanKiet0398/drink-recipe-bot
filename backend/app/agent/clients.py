from functools import lru_cache

from chromadb import PersistentClient
from openai import OpenAI
from sqlalchemy.orm import Session

from app import llm_settings
from app.config import get_settings

# The chat client and model are cached across requests and cleared by
# invalidate_chat_client() when settings change, so a provider switch takes
# effect on the next message without a restart.
#
# This is correct ONLY because the backend runs a single uvicorn process
# (see backend/Dockerfile — no --workers). With more than one worker each
# would hold its own stale copy and a save would take effect unevenly.
_chat_cache: dict[str, object] = {}


@lru_cache
def get_embedding_client() -> OpenAI:
    """Embeddings always go to OpenAI.

    The Chroma index is built with text-embedding-3-small; routing this
    through the configured chat provider would invalidate every vector.
    """
    return OpenAI(api_key=get_settings().openai_api_key)


def build_chat_client(provider: str, base_url: str | None, api_key: str) -> OpenAI:
    """Construct a chat client from explicit values, without touching the DB
    or the cache. Used both by get_chat_client and by the settings test
    endpoint, which must never disturb the client serving customers."""
    # The SDK rejects an empty api_key. Ollama ignores whatever is sent, so a
    # placeholder keeps a credential-free provider working.
    if not api_key and provider == "ollama":
        api_key = "ollama"
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def invalidate_chat_client() -> None:
    _chat_cache.clear()


def _resolved(db: Session) -> llm_settings.ResolvedSettings:
    cached = _chat_cache.get("resolved")
    if cached is None:
        cached = llm_settings.resolve(db)
        _chat_cache["resolved"] = cached
    return cached  # type: ignore[return-value]


def get_chat_client(db: Session) -> OpenAI:
    client = _chat_cache.get("client")
    if client is None:
        resolved = _resolved(db)
        client = build_chat_client(resolved.provider, resolved.base_url, resolved.api_key)
        _chat_cache["client"] = client
    return client  # type: ignore[return-value]


def get_chat_model(db: Session) -> str:
    return _resolved(db).chat_model


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
