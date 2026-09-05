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
