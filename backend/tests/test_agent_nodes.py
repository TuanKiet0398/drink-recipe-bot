from unittest.mock import MagicMock

from app.agent.nodes import fetch_history, retrieve, generate
from app.agent.state import AgentState
from app.db.models import User, Message, Favourite


def test_fetch_history_loads_recent_messages_and_favourites(db_session):
    user = User(telegram_user_id="99")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Message(user_id=user.id, role="assistant", content="hello!"))
    db_session.add(Favourite(user_id=user.id, drink_name="hojicha"))
    db_session.commit()

    state = AgentState(user_id=user.id, chat_id="99", incoming_text="what do you recommend?")
    result = fetch_history(state, db_session)

    assert len(result.history) == 2
    assert result.history[0]["content"] == "hi"
    assert result.favourites == ["hojicha"]


def test_retrieve_queries_qdrant_and_fills_chunks():
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_point = MagicMock()
    fake_point.payload = {"text": "Whisk matcha with a bamboo chasen."}
    fake_qdrant = MagicMock()
    fake_qdrant.search.return_value = [fake_point]

    result = retrieve(state, qdrant_client=fake_qdrant, openai_client=fake_openai)

    fake_openai.embeddings.create.assert_called_once()
    fake_qdrant.search.assert_called_once()
    assert result.retrieved_chunks == ["Whisk matcha with a bamboo chasen."]


def test_generate_calls_openai_with_context_and_sets_reply():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="what matcha do you recommend?",
        history=[{"role": "user", "content": "hi"}],
        favourites=["hojicha"],
        retrieved_chunks=["Ceremonial grade matcha is best whisked, not shaken."],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Try our ceremonial grade matcha!"))
    ]

    result = generate(state, openai_client=fake_openai)

    fake_openai.chat.completions.create.assert_called_once()
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    system_message = call_kwargs["messages"][0]["content"]
    assert "hojicha" in system_message
    assert "Ceremonial grade matcha is best whisked, not shaken." in system_message
    assert result.reply == "Try our ceremonial grade matcha!"
