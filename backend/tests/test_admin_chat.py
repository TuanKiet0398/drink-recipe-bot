from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.db.models import Channel, ConversationSummary, CustomerNote, Favourite, Message, User

PASSWORD = "matcha-lover"


def register(client, username: str) -> tuple[str, str]:
    response = client.post("/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201
    return (username, PASSWORD)


@pytest.fixture()
def agent(monkeypatch):
    """Runs the real graph (so the real fetch_history reads the database) with
    retrieve/generate faked, and records what generate saw."""
    seen = {"generate": [], "spawned": []}

    def fake_retrieve(state, db, chroma_client, chat_client, embedding_client, chat_model):
        state.retrieved_chunks = ["Iced matcha: 2g matcha, 30ml water."]
        return state

    def fake_generate(state, db, chat_client, model, on_delta=None):
        seen["generate"].append({"incoming": state.incoming_text, "history": list(state.history)})
        state.reply = f"reply to {state.incoming_text}"
        return state

    monkeypatch.setattr("app.agent.graph.retrieve", fake_retrieve)
    monkeypatch.setattr("app.agent.graph.generate", fake_generate)
    monkeypatch.setattr("app.routers.admin_chat.get_chroma_client", lambda: object())
    monkeypatch.setattr("app.routers.admin_chat.get_embedding_client", lambda: object())
    monkeypatch.setattr("app.routers.admin_chat.get_chat_client", lambda db: object())
    monkeypatch.setattr("app.routers.admin_chat.get_chat_model", lambda db: "gpt-4o-mini")
    monkeypatch.setattr(
        "app.routers.admin_chat.spawn_background_extractions",
        lambda state, user_id: seen["spawned"].append((user_id, state.reply, list(state.retrieved_chunks))),
    )
    return seen


def test_chat_endpoints_require_auth(client):
    assert client.post("/admin/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/admin/chat/history").status_code == 401
    assert client.delete("/admin/chat/history").status_code == 401


@pytest.mark.parametrize("message", ["", "   ", "x" * 4001])
def test_rejects_blank_or_oversized_messages(client, agent, message):
    auth = register(client, "linh")
    assert client.post("/admin/chat", auth=auth, json={"message": message}).status_code == 422


def test_first_message_creates_the_web_channel_and_user(client, db_session, agent):
    auth = register(client, "linh")

    response = client.post("/admin/chat", auth=auth, json={"message": "Cách pha matcha đá?"})

    assert response.status_code == 200
    assert response.json() == {"reply": "reply to Cách pha matcha đá?", "model": "gpt-4o-mini"}
    channel = db_session.query(Channel).filter_by(key="web").one()
    assert channel.channel_type == "web"
    user = db_session.query(User).filter_by(channel_id=channel.id, telegram_user_id="linh").one()
    assert user.last_active_at is not None


def test_history_given_to_the_agent_excludes_the_current_message(client, agent):
    auth = register(client, "linh")

    client.post("/admin/chat", auth=auth, json={"message": "first"})
    client.post("/admin/chat", auth=auth, json={"message": "second"})

    assert agent["generate"][0] == {"incoming": "first", "history": []}
    assert agent["generate"][1] == {
        "incoming": "second",
        "history": [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply to first"},
        ],
    }


def test_a_turn_saves_both_messages_and_starts_background_extraction(client, db_session, agent):
    auth = register(client, "linh")

    client.post("/admin/chat", auth=auth, json={"message": "hello"})

    user = db_session.query(User).filter_by(telegram_user_id="linh").one()
    messages = db_session.query(Message).filter_by(user_id=user.id).order_by(Message.id).all()
    assert [(m.role, m.content) for m in messages] == [("user", "hello"), ("assistant", "reply to hello")]
    assert agent["spawned"] == [(user.id, "reply to hello", ["Iced matcha: 2g matcha, 30ml water."])]


def test_the_env_admin_chats_with_memory_too(client, db_session, agent):
    settings = get_settings()

    response = client.post(
        "/admin/chat", auth=(settings.admin_username, settings.admin_password), json={"message": "hi"}
    )

    assert response.status_code == 200
    assert db_session.query(User).filter_by(telegram_user_id=settings.admin_username).count() == 1


def test_a_blocked_user_cannot_chat(client, db_session, agent):
    auth = register(client, "linh")
    client.post("/admin/chat", auth=auth, json={"message": "hello"})
    user = db_session.query(User).filter_by(telegram_user_id="linh").one()
    user.blocked = True
    db_session.commit()

    response = client.post("/admin/chat", auth=auth, json={"message": "again"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Your account is blocked"
    assert len(agent["generate"]) == 1


def test_daily_limit_replies_without_calling_the_agent(client, db_session, agent, monkeypatch):
    from app.routers.webhook import DAILY_LIMIT_REPLY

    monkeypatch.setattr("app.llm_settings.resolve", lambda db: SimpleNamespace(daily_token_limit=1000))
    monkeypatch.setattr("app.routers.admin_chat.get_daily_token_total", lambda db, user_id: 1000)
    auth = register(client, "linh")

    response = client.post("/admin/chat", auth=auth, json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["reply"] == DAILY_LIMIT_REPLY
    assert agent["generate"] == []
    assert [m.role for m in db_session.query(Message).order_by(Message.id)] == ["user", "assistant"]


def test_agent_failure_returns_502_and_keeps_only_the_user_message(client, db_session, agent, monkeypatch):
    def broken_generate(state, db, chat_client, model, on_delta=None):
        raise RuntimeError("Incorrect API key provided")

    monkeypatch.setattr("app.agent.graph.generate", broken_generate)
    auth = register(client, "linh")

    response = client.post("/admin/chat", auth=auth, json={"message": "hello"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Incorrect API key provided"
    assert [(m.role, m.content) for m in db_session.query(Message)] == [("user", "hello")]
    assert agent["spawned"] == []


def test_history_returns_only_the_callers_messages(client, agent):
    linh = register(client, "linh")
    minh = register(client, "minh")
    client.post("/admin/chat", auth=linh, json={"message": "from linh"})
    client.post("/admin/chat", auth=minh, json={"message": "from minh"})

    response = client.get("/admin/chat/history", auth=linh)

    assert response.status_code == 200
    body = response.json()
    assert [(m["role"], m["content"]) for m in body] == [
        ("user", "from linh"),
        ("assistant", "reply to from linh"),
    ]
    assert all(m["created_at"] for m in body)


def test_reset_clears_history_and_summary_but_keeps_preferences(client, db_session, agent):
    linh = register(client, "linh")
    minh = register(client, "minh")
    client.post("/admin/chat", auth=linh, json={"message": "hello"})
    client.post("/admin/chat", auth=minh, json={"message": "hello"})
    user = db_session.query(User).filter_by(telegram_user_id="linh").one()
    db_session.add_all(
        [
            Favourite(user_id=user.id, drink_name="Hojicha Latte"),
            CustomerNote(user_id=user.id, note_type="allergy", value="nuts"),
            ConversationSummary(user_id=user.id, summary_text="Likes hojicha."),
        ]
    )
    db_session.commit()

    response = client.delete("/admin/chat/history", auth=linh)

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 0
    assert db_session.query(ConversationSummary).filter_by(user_id=user.id).count() == 0
    assert db_session.query(Favourite).filter_by(user_id=user.id).count() == 1
    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 1
    minh_user = db_session.query(User).filter_by(telegram_user_id="minh").one()
    assert db_session.query(Message).filter_by(user_id=minh_user.id).count() == 2


def test_channel_list_hides_the_web_channel(client, agent):
    auth = register(client, "linh")
    client.post("/admin/chat", auth=auth, json={"message": "hello"})

    response = client.get("/admin/channels", auth=auth)

    assert response.status_code == 200
    assert all(c["channel_type"] != "web" for c in response.json())
