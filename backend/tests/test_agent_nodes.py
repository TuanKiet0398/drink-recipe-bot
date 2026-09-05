import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.agent.nodes import fetch_history, retrieve, rerank, rewrite_query, generate, extract_favourite
from app.agent.state import AgentState
from app.db.models import User, Message, Favourite
from app.retry import retry_once


def _fake_stream(*content_pieces, usage=None):
    """Builds a fake OpenAI streaming response: an iterable of chunk objects,
    one per content piece, plus a trailing usage-only chunk (mirroring
    `stream_options={"include_usage": True}`'s final chunk shape)."""
    chunks = []
    for piece in content_pieces:
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content=piece))]
        chunk.usage = None
        chunks.append(chunk)
    final = MagicMock()
    final.choices = []
    final.usage = usage
    chunks.append(final)
    return chunks


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


def _fake_chroma(query_results):
    """query_results: a list of {"documents": [[...]], "distances": [[...]]}
    dicts, consumed in order by successive collection.query() calls."""
    fake_collection = MagicMock()
    fake_collection.query.side_effect = query_results
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    return fake_chroma, fake_collection


def _fake_openai_with_rewrite(embedding=None, rewritten_text=None):
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=embedding or [0.1, 0.2, 0.3])]
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=rewritten_text or "how to brew matcha?"))
    ]
    fake_openai.chat.completions.create.return_value.usage = None
    return fake_openai


def test_retrieve_returns_top_chunk_above_threshold(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_chroma, fake_collection = _fake_chroma(
        [{"documents": [["Whisk matcha with a bamboo chasen."]], "distances": [[0.1]]}]
    )

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == ["Whisk matcha with a bamboo chasen."]
    # The rewritten query is identical to the original, so only one
    # embed+query round trip happens (no redundant second search).
    fake_collection.query.assert_called_once()


def test_retrieve_filters_out_hits_below_score_threshold(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how do I brew coffee?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how do I brew coffee?")
    # distance=0.9 -> score=0.1, below the 0.20 default threshold
    fake_chroma, _ = _fake_chroma([{"documents": [["irrelevant tea chunk"]], "distances": [[0.9]]}])

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_searches_twice_and_merges_when_rewrite_differs(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="cách pha trà xanh")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew green tea")
    fake_openai.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="how to brew green tea"))], usage=None),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"order": [2, 1]})))], usage=None),
    ]
    fake_chroma, fake_collection = _fake_chroma(
        [
            {"documents": [["Chunk A"]], "distances": [[0.2]]},
            {"documents": [["Chunk B"]], "distances": [[0.1]]},
        ]
    )

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert fake_collection.query.call_count == 2
    # Merged order by score would be [Chunk B (0.9), Chunk A (0.8)];
    # rerank's order=[2, 1] flips that to [Chunk A, Chunk B].
    assert result.retrieved_chunks == ["Chunk A", "Chunk B"]


def test_retrieve_tolerates_chroma_query_failure_and_returns_empty_chunks(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_collection = MagicMock()
    fake_collection.query.side_effect = RuntimeError("collection not found")
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert result.retrieved_chunks == []


def test_retrieve_retries_openai_embedding_once_then_succeeds(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="how to brew matcha?")
    fake_openai = _fake_openai_with_rewrite(rewritten_text="how to brew matcha?")
    fake_openai.embeddings.create.side_effect = [
        RuntimeError("transient"),
        MagicMock(data=[MagicMock(embedding=[0.1, 0.2, 0.3])]),
    ]
    fake_chroma, _ = _fake_chroma([{"documents": [[]], "distances": [[]]}])

    with patch("app.retry.time.sleep"):
        result = retrieve(state, db_session, chroma_client=fake_chroma, openai_client=fake_openai)

    assert fake_openai.embeddings.create.call_count == 2
    assert result.retrieved_chunks == []


def test_rewrite_query_falls_back_to_original_question_when_llm_fails():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("down")

    with patch("app.retry.time.sleep"):
        result = rewrite_query("how to brew matcha?", [], fake_openai, db=MagicMock(), user_id=1)

    assert result == "how to brew matcha?"


def test_rerank_reorders_chunks_by_llm_response():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"order": [2, 1]})))
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    result = rerank("q", ["first", "second"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["second", "first"]


def test_rerank_keeps_original_order_when_llm_response_is_incomplete():
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"order": [1]})))  # missing chunk 2
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    result = rerank("q", ["first", "second"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["first", "second"]


def test_rerank_skips_llm_call_for_a_single_chunk():
    fake_openai = MagicMock()

    result = rerank("q", ["only chunk"], fake_openai, db=MagicMock(), user_id=1)

    assert result == ["only chunk"]
    fake_openai.chat.completions.create.assert_not_called()


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
    fake_openai.chat.completions.create.return_value = _fake_stream("Try our ceremonial grade matcha!")

    result = generate(state, db_session, openai_client=fake_openai)

    fake_openai.chat.completions.create.assert_called_once()
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is True
    system_message = call_kwargs["messages"][0]["content"]
    assert "hojicha" in system_message
    assert "Ceremonial grade matcha is best whisked, not shaken." in system_message
    assert result.reply == "Try our ceremonial grade matcha!"


def test_generate_calls_on_delta_with_accumulated_text_as_chunks_arrive(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="what matcha do you recommend?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_stream("Try ", "our ", "matcha!")

    seen: list[str] = []
    result = generate(state, db_session, openai_client=fake_openai, on_delta=seen.append)

    assert seen == ["Try ", "Try our ", "Try our matcha!"]
    assert result.reply == "Try our matcha!"


def test_generate_swallows_on_delta_errors(db_session):
    state = AgentState(user_id=1, chat_id="1", incoming_text="what matcha do you recommend?")

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_stream("Try our matcha!")

    def broken_on_delta(_text: str) -> None:
        raise RuntimeError("delivery failed")

    result = generate(state, db_session, openai_client=fake_openai, on_delta=broken_on_delta)

    assert result.reply == "Try our matcha!"


def test_generate_system_prompt_restricts_recommendations_to_retrieved_knowledge():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="do you have bubble tea?",
        retrieved_chunks=["Matcha latte: whisk 2g matcha with steamed milk."],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_stream(
        "We don't have that, but try our matcha latte!"
    )

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
    fake_openai.chat.completions.create.return_value = _fake_stream("Sorry, we don't carry coffee here.")

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
        _fake_stream("Try ceremonial grade!"),
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
