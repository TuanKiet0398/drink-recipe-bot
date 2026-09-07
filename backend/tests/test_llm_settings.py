from app import llm_settings
from app.db.models import LLMSettings


def test_resolve_falls_back_to_the_environment_when_unconfigured(db_session):
    resolved = llm_settings.resolve(db_session)

    assert resolved.provider == "openai"
    assert resolved.base_url is None
    assert resolved.chat_model == llm_settings.DEFAULT_CHAT_MODEL
    assert resolved.is_default is True
    assert resolved.api_key != ""


def test_save_creates_the_singleton_row(db_session):
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key="secret-key",
        chat_model="llama3.1",
        updated_by="admin",
    )

    rows = db_session.query(LLMSettings).all()
    assert len(rows) == 1
    assert rows[0].id == 1


def test_save_twice_updates_rather_than_inserting(db_session):
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="k1",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://x:11434/v1",
        api_key="k2",
        chat_model="llama3.1",
        updated_by="admin",
    )

    rows = db_session.query(LLMSettings).all()
    assert len(rows) == 1
    assert rows[0].provider == "ollama"


def test_resolve_returns_the_stored_configuration(db_session):
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://ollama.local:11434/v1",
        api_key="secret-key",
        chat_model="llama3.1",
        updated_by="admin",
    )

    resolved = llm_settings.resolve(db_session)

    assert resolved.provider == "ollama"
    assert resolved.base_url == "http://ollama.local:11434/v1"
    assert resolved.api_key == "secret-key"
    assert resolved.chat_model == "llama3.1"
    assert resolved.is_default is False


def test_the_api_key_is_encrypted_at_rest(db_session):
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-plaintext",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )

    stored = db_session.query(LLMSettings).one().encrypted_api_key
    assert stored is not None
    assert "sk-plaintext" not in stored


def test_saving_with_no_key_keeps_the_stored_one(db_session):
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-original",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )

    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key=None,
        chat_model="gpt-4o",
        updated_by="admin",
    )

    resolved = llm_settings.resolve(db_session)
    assert resolved.api_key == "sk-original"
    assert resolved.chat_model == "gpt-4o"


def test_an_ollama_row_with_no_key_resolves_to_an_empty_key(db_session):
    # Ollama needs no credentials; the SDK still requires a non-None api_key,
    # so an empty string is the resolved value and the client factory
    # substitutes a placeholder.
    llm_settings.save(
        db_session,
        provider="ollama",
        base_url="http://x:11434/v1",
        api_key=None,
        chat_model="llama3.1",
        updated_by="admin",
    )

    assert llm_settings.resolve(db_session).api_key == ""


def test_read_row_returns_none_when_unconfigured(db_session):
    assert llm_settings.read_row(db_session) is None


def test_providers_are_exactly_openai_and_ollama():
    assert llm_settings.PROVIDERS == ("openai", "ollama")
