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


def test_get_embedding_client_uses_the_environment_key():
    from app.agent.clients import get_embedding_client

    client = get_embedding_client()

    assert client.api_key == "test-key-not-real"


def test_get_chat_client_falls_back_to_the_environment(db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    client = get_chat_client(db_session)

    assert client.api_key == "test-key-not-real"


def test_get_chat_client_honours_a_configured_base_url(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_client, invalidate_chat_client

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    client = get_chat_client(db_session)

    assert str(client.base_url).rstrip("/") == "http://ollama.local:11434/v1"


def test_get_chat_client_is_cached_until_invalidated(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    first = get_chat_client(db_session)
    assert get_chat_client(db_session) is first

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    assert get_chat_client(db_session) is not first


def test_get_chat_model_falls_back_to_the_default(db_session):
    from app.agent.clients import get_chat_model, invalidate_chat_client

    invalidate_chat_client()

    assert get_chat_model(db_session) == "gpt-4o-mini"


def test_get_chat_model_returns_the_configured_model(db_session):
    from app import llm_settings
    from app.agent.clients import get_chat_model, invalidate_chat_client

    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://x:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )
    invalidate_chat_client()

    assert get_chat_model(db_session) == "llama3.1"


def test_build_chat_client_substitutes_a_placeholder_key_for_ollama():
    from app.agent.clients import build_chat_client

    client = build_chat_client("ollama", "http://x:11434/v1", "")

    # The OpenAI SDK refuses an empty api_key, and Ollama ignores it.
    assert client.api_key == "ollama"


def test_get_openai_client_is_gone():
    import app.agent.clients as clients

    assert not hasattr(clients, "get_openai_client")
