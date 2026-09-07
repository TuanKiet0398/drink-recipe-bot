from unittest.mock import MagicMock, patch

import pytest

from app import llm_settings
from app.db.models import AdminAuditLog

AUTH = ("admin", "admin")

BUILD_CLIENT = "app.routers.admin_llm_settings.build_chat_client"


@pytest.fixture()
def fake_provider():
    """Replace the throwaway client the test endpoint builds.

    The OpenAI SDK talks httpx2, which respx cannot intercept, so stubbing at
    the HTTP layer would let these tests reach the real API. Patching the
    factory keeps them offline and still records the arguments the endpoint
    resolved, which is what the assertions are about.
    """
    client = MagicMock()
    with patch(BUILD_CLIENT, return_value=client) as factory:
        yield factory, client


def test_endpoints_require_auth(client):
    assert client.get("/admin/llm-settings").status_code == 401
    assert client.put("/admin/llm-settings", json={}).status_code == 401
    assert client.post("/admin/llm-settings/test", json={}).status_code == 401


def test_get_reports_the_default_when_unconfigured(client):
    body = client.get("/admin/llm-settings", auth=AUTH).json()

    assert body["is_default"] is True
    assert body["provider"] == "openai"
    assert body["chat_model"] == "gpt-4o-mini"
    assert body["has_api_key"] is True
    assert "api_key" not in body


def test_get_never_returns_the_api_key(client, db_session):
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-secret",
        chat_model="gpt-4o",
        updated_by="admin",
    )

    response = client.get("/admin/llm-settings", auth=AUTH)

    assert "sk-secret" not in response.text
    body = response.json()
    assert body["has_api_key"] is True
    assert body["is_default"] is False
    assert body["chat_model"] == "gpt-4o"


def test_put_rejects_an_unknown_provider(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "anthropic", "chat_model": "claude", "base_url": None, "api_key": "k"},
    )

    assert response.status_code == 400


def test_put_rejects_ollama_without_a_base_url(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "ollama", "chat_model": "llama3.1", "base_url": None, "api_key": None},
    )

    assert response.status_code == 400


def test_put_rejects_an_empty_chat_model(client):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "  ", "base_url": None, "api_key": "k"},
    )

    assert response.status_code == 400


def test_put_saves_and_audits_without_leaking_the_key(client, db_session):
    response = client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": "sk-should-not-appear",
        },
    )

    assert response.status_code == 200
    assert llm_settings.resolve(db_session).chat_model == "llama3.1"

    entries = db_session.query(AdminAuditLog).filter_by(action="llm_settings.update").all()
    assert len(entries) == 1
    assert "sk-should-not-appear" not in (entries[0].target or "")


def test_test_endpoint_reports_success(client, fake_provider):
    _, provider = fake_provider

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": None,
        },
    ).json()

    assert body["ok"] is True
    assert body["model"] == "llama3.1"
    assert isinstance(body["latency_ms"], int)
    assert provider.chat.completions.create.call_args.kwargs["model"] == "llama3.1"


def test_test_endpoint_reports_a_provider_failure(client, fake_provider):
    _, provider = fake_provider
    provider.chat.completions.create.side_effect = RuntimeError("Incorrect API key provided")

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-bad"},
    ).json()

    assert body["ok"] is False
    assert "Incorrect API key" in body["error"]


def test_test_endpoint_writes_no_token_usage(client, db_session, fake_provider):
    from app.db.models import TokenUsage

    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-good"},
    )

    assert db_session.query(TokenUsage).count() == 0


def test_test_endpoint_records_no_retry_metric(client, fake_provider):
    from prometheus_client import REGISTRY

    def _total_retries() -> float:
        # Sum every call_type: asserting on one label would pass trivially,
        # because a series that was never touched reads as absent.
        total = 0.0
        for metric in REGISTRY.collect():
            if metric.name == "llm_retries":
                total += sum(sample.value for sample in metric.samples)
        return total

    _, provider = fake_provider
    provider.chat.completions.create.side_effect = RuntimeError("boom")
    before = _total_retries()

    body = client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-good"},
    ).json()

    assert body["ok"] is False
    # One attempt only: the endpoint must not wrap the call in retry_once.
    assert provider.chat.completions.create.call_count == 1
    assert _total_retries() == before


def test_test_endpoint_uses_the_stored_key_when_none_is_supplied(client, db_session, fake_provider):
    factory, _ = fake_provider
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-stored",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )

    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": None},
    )

    assert factory.call_args.args == ("openai", None, "sk-stored")


def test_test_endpoint_prefers_a_supplied_key_over_the_stored_one(client, db_session, fake_provider):
    factory, _ = fake_provider
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-stored",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )

    client.post(
        "/admin/llm-settings/test",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o-mini", "base_url": None, "api_key": "sk-new"},
    )

    assert factory.call_args.args == ("openai", None, "sk-new")


def test_test_endpoint_leaves_the_cached_client_alone(client, db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    before = get_chat_client(db_session)

    with patch(BUILD_CLIENT, return_value=MagicMock()):
        client.post(
            "/admin/llm-settings/test",
            auth=AUTH,
            json={
                "provider": "ollama",
                "chat_model": "llama3.1",
                "base_url": "http://ollama.local:11434/v1",
                "api_key": None,
            },
        )

    assert get_chat_client(db_session) is before


def test_put_invalidates_the_cached_client(client, db_session):
    from app.agent.clients import get_chat_client, invalidate_chat_client

    invalidate_chat_client()
    before = get_chat_client(db_session)

    client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={
            "provider": "ollama",
            "chat_model": "llama3.1",
            "base_url": "http://ollama.local:11434/v1",
            "api_key": None,
        },
    )

    assert get_chat_client(db_session) is not before


def test_put_with_a_blank_key_keeps_the_stored_one(client, db_session):
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="sk-keep",
        chat_model="gpt-4o-mini",
        updated_by="admin",
    )

    client.put(
        "/admin/llm-settings",
        auth=AUTH,
        json={"provider": "openai", "chat_model": "gpt-4o", "base_url": None, "api_key": None},
    )

    resolved = llm_settings.resolve(db_session)
    assert resolved.api_key == "sk-keep"
    assert resolved.chat_model == "gpt-4o"
