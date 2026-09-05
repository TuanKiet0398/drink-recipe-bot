from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.agent.nodes import fetch_history, retrieve, generate, extract_favourite
from app.agent.state import AgentState
from app.db.models import User, Message, Favourite
from app.retry import retry_once


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


def test_fetch_history_returns_last_n_messages_in_chronological_order(db_session):
    user = User(telegram_user_id="100")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    base = datetime.now(timezone.utc)
    for i in range(15):
        db_session.add(
            Message(
                user_id=user.id,
                role="user",
                content=f"message-{i}",
                created_at=base + timedelta(seconds=i),
            )
        )
    db_session.commit()

    state = AgentState(user_id=user.id, chat_id="100", incoming_text="what do you recommend?")
    result = fetch_history(state, db_session, limit=10)

    assert len(result.history) == 10
    contents = [m["content"] for m in result.history]
    assert contents == [f"message-{i}" for i in range(5, 15)]


def test_retrieve_queries_qdrant_and_fills_chunks(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_point = MagicMock()
    fake_point.payload = {"text": "Whisk matcha with a bamboo chasen."}
    fake_qdrant = MagicMock()
    fake_qdrant.collection_exists.return_value = True
    fake_qdrant.query_points.return_value = MagicMock(points=[fake_point])

    result = retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    fake_openai.embeddings.create.assert_called_once()
    fake_qdrant.query_points.assert_called_once()
    assert fake_qdrant.query_points.call_args.kwargs["score_threshold"] == 0.35
    assert result.retrieved_chunks == ["Whisk matcha with a bamboo chasen."]


def test_retrieve_returns_no_chunks_when_qdrant_filters_everything_below_threshold(db_session):
    # Simulates asking about something the shop's knowledge base has
    # nothing relevant to (e.g. coffee, when only tea/matcha is stocked):
    # Qdrant's score_threshold means no hits come back at all, rather than
    # the nearest-but-irrelevant tea chunks.
    state = AgentState(user_id=1, chat_id="1", incoming_text="how do I brew coffee?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_qdrant = MagicMock()
    fake_qdrant.collection_exists.return_value = True
    fake_qdrant.query_points.return_value = MagicMock(points=[])

    result = retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_creates_collection_when_missing(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_qdrant = MagicMock()
    fake_qdrant.collection_exists.return_value = False
    fake_qdrant.query_points.return_value = MagicMock(points=[])

    retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    fake_qdrant.create_collection.assert_called_once()


def test_retrieve_tolerates_search_failure_and_returns_empty_chunks(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    fake_qdrant = MagicMock()
    fake_qdrant.collection_exists.return_value = True
    fake_qdrant.query_points.side_effect = RuntimeError("collection not found")

    result = retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_retries_openai_embedding_once_then_succeeds(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.side_effect = [
        RuntimeError("transient"),
        MagicMock(data=[MagicMock(embedding=[0.1, 0.2, 0.3])]),
    ]

    fake_qdrant = MagicMock()
    fake_qdrant.collection_exists.return_value = True
    fake_qdrant.query_points.return_value = MagicMock(points=[])

    with patch("app.retry.time.sleep"):
        result = retrieve(state, db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    assert fake_openai.embeddings.create.call_count == 2
    assert result.retrieved_chunks == []


def test_generate_calls_openai_with_context_and_sets_reply(db_session):
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

    result = generate(state, db_session, openai_client=fake_openai)

    fake_openai.chat.completions.create.assert_called_once()
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    system_message = call_kwargs["messages"][0]["content"]
    assert "hojicha" in system_message
    assert "Ceremonial grade matcha is best whisked, not shaken." in system_message
    assert result.reply == "Try our ceremonial grade matcha!"


def test_generate_system_prompt_restricts_recommendations_to_retrieved_knowledge():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="do you have bubble tea?",
        retrieved_chunks=["Matcha latte: whisk 2g matcha with steamed milk."],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="We don't have that, but try our matcha latte!"))
    ]

    generate(state, MagicMock(), openai_client=fake_openai)

    system_message = fake_openai.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "only recommend" in system_message.lower()
    assert "never invent" in system_message.lower()


def test_generate_system_prompt_forbids_answering_when_no_knowledge_matched():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="how do I brew coffee?",
        retrieved_chunks=[],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Sorry, we don't carry coffee here."))
    ]

    generate(state, MagicMock(), openai_client=fake_openai)

    system_message = fake_openai.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "(no matching knowledge found)" in system_message
    assert "do not describe how to make the drink" in system_message.lower()


def test_extract_favourite_upserts_when_preference_detected(db_session):
    user = User(telegram_user_id="7")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="7", incoming_text="I really love sencha the most")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": "sencha"}'))
    ]

    extract_favourite(state, db=db_session, openai_client=fake_openai)

    rows = db_session.query(Favourite).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].drink_name == "sencha"


def test_generate_retries_openai_once_then_succeeds(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="what matcha do you recommend?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        RuntimeError("transient"),
        MagicMock(choices=[MagicMock(message=MagicMock(content="Try ceremonial grade!"))]),
    ]

    with patch("app.retry.time.sleep"):
        result = generate(state, db_session, openai_client=fake_openai)

    assert fake_openai.chat.completions.create.call_count == 2
    assert result.reply == "Try ceremonial grade!"


def test_generate_propagates_when_both_attempts_fail(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="what matcha do you recommend?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("still down")

    with patch("app.retry.time.sleep"):
        with pytest.raises(RuntimeError):
            generate(state, db_session, openai_client=fake_openai)

    assert fake_openai.chat.completions.create.call_count == 2


def test_retry_once_returns_result_on_first_success():
    fn = MagicMock(return_value="ok")
    assert retry_once(fn) == "ok"
    assert fn.call_count == 1


def test_retry_once_retries_and_succeeds():
    fn = MagicMock(side_effect=[RuntimeError("boom"), "ok"])
    with patch("app.retry.time.sleep"):
        assert retry_once(fn) == "ok"
    assert fn.call_count == 2


def test_retry_once_propagates_when_both_attempts_fail():
    fn = MagicMock(side_effect=RuntimeError("boom"))
    with patch("app.retry.time.sleep"):
        with pytest.raises(RuntimeError):
            retry_once(fn)
    assert fn.call_count == 2


def test_extract_favourite_noop_when_no_preference(db_session):
    user = User(telegram_user_id="8")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="8", incoming_text="what time do you close?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": null}'))
    ]

    extract_favourite(state, db=db_session, openai_client=fake_openai)

    assert db_session.query(Favourite).filter_by(user_id=user.id).count() == 0
