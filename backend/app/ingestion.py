import uuid

from app.agent.clients import ensure_collection


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks or [text]


def embed_and_upsert(
    chunks: list[str],
    filename: str,
    document_id: int,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
) -> None:
    from qdrant_client.models import PointStruct

    ensure_collection(qdrant_client, collection=collection)

    points = []
    for chunk in chunks:
        embedding = (
            openai_client.embeddings.create(model="text-embedding-3-small", input=chunk)
            .data[0]
            .embedding
        )
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={"text": chunk, "source": filename, "document_id": document_id},
            )
        )
    qdrant_client.upsert(collection_name=collection, points=points)
