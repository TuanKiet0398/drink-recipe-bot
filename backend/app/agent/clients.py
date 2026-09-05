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
