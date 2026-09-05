from functools import lru_cache

from openai import OpenAI
from qdrant_client import QdrantClient

from app.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


def ensure_collection(qdrant_client, collection: str = "matcha_knowledge", vector_size: int = 1536) -> None:
    """Idempotently make sure `collection` exists in Qdrant.

    Cheap enough to call before every upload/search — avoids requiring an
    operator to manually create the collection against a fresh Qdrant
    instance before the bot can be used.
    """
    from qdrant_client.models import Distance, VectorParams

    if qdrant_client.collection_exists(collection):
        return

    try:
        qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    except Exception as exc:  # noqa: BLE001 - tolerate races where another
        # process/request created the collection between the exists-check
        # and create_collection call.
        if "already exists" not in str(exc).lower():
            raise
