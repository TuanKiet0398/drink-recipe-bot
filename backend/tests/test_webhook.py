import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import Message, User
from app.routers.webhook import THINKING_PLACEHOLDER, _get_or_create_user, process_telegram_message


@pytest.mark.asyncio
async def test_process_message_creates_user_stores_message_and_replies(db_session, channel_id):
    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock) as mock_send,
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock) as mock_edit,
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock) as mock_typing,
        patch("app.routers.webhook.extract_favourite"),
        patch("app.routers.webhook.get_chroma_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_chat_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_embedding_client", return_value=MagicMock()),
    ):
        mock_send.return_value = 555

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(channel_id, "TEST_TOKEN", "111", "111", "hi there", db_session)

    mock_send.assert_awaited_once()
    assert mock_send.call_args.args[0] == "TEST_TOKEN"
    assert mock_send.call_args.kwargs["text"] == THINKING_PLACEHOLDER
    mock_edit.assert_awaited_once_with("TEST_TOKEN", chat_id="111", message_id=555, text="Welcome!")
    mock_typing.assert_awaited_once_with("TEST_TOKEN", chat_id="111", action="typing")
    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="111").one()
    assert user is not None


@pytest.mark.asyncio
async def test_process_message_delivers_streamed_reply_progressively(db_session, channel_id):
    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock) as mock_send,
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock) as mock_edit,
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.extract_favourite"),
        patch("app.routers.webhook.get_chroma_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_chat_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_embedding_client", return_value=MagicMock()),
    ):
        mock_send.return_value = 999

        def fake_run_agent(state, **kwargs):
            on_delta = kwargs["on_delta"]
            on_delta("Try ")
            on_delta("Try our matcha!")
            state.reply = "Try our matcha!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(channel_id, "TEST_TOKEN", "222", "222", "hi there", db_session)

    mock_send.assert_awaited_once()
    assert mock_send.call_args.kwargs["text"] == THINKING_PLACEHOLDER
    assert mock_edit.await_count == 2
    mock_edit.assert_any_await("TEST_TOKEN", chat_id="222", message_id=999, text="Try ")
    mock_edit.assert_awaited_with("TEST_TOKEN", chat_id="222", message_id=999, text="Try our matcha!")


@pytest.mark.asyncio
async def test_keepalive_typing_refreshes_on_each_interval_tick():
    from app.routers.webhook import _keepalive_typing

    with (
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock) as mock_typing,
        patch("app.routers.webhook._TYPING_KEEPALIVE_INTERVAL", 0.02),
    ):
        task = asyncio.create_task(_keepalive_typing("TEST_TOKEN", chat_id="444", user_id=1))
        await asyncio.sleep(0.09)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert mock_typing.await_count >= 3
    mock_typing.assert_awaited_with("TEST_TOKEN", chat_id="444", action="typing")


@pytest.mark.asyncio
async def test_keepalive_typing_survives_a_send_chat_action_failure():
    from app.routers.webhook import _keepalive_typing

    with (
        patch(
            "app.routers.webhook.send_chat_action", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ) as mock_typing,
        patch("app.routers.webhook._TYPING_KEEPALIVE_INTERVAL", 0.02),
    ):
        task = asyncio.create_task(_keepalive_typing("TEST_TOKEN", chat_id="444", user_id=1))
        await asyncio.sleep(0.07)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert mock_typing.await_count >= 2


@pytest.mark.asyncio
async def test_process_message_skips_blocked_user(db_session, channel_id):
    blocked = User(channel_id=channel_id, telegram_user_id="222", blocked=True)
    db_session.add(blocked)
    db_session.commit()

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await process_telegram_message(channel_id, "TEST_TOKEN", "222", "222", "hello", db_session)

    mock_run_agent.assert_not_called()
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_swallows_send_message_failures(db_session, channel_id):
    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock) as mock_send,
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.extract_favourite"),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent
        mock_send.side_effect = RuntimeError("Telegram API error")

        await process_telegram_message(channel_id, "TEST_TOKEN", "333", "333", "hi there", db_session)

    assert mock_send.await_count == 2
    mock_send.assert_awaited_with("TEST_TOKEN", chat_id="333", text="Welcome!")
    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="333").one()
    assert user is not None


@pytest.mark.asyncio
async def test_process_message_background_favourite_extraction_actually_runs(db_session, channel_id):
    from tests.conftest import TestSessionLocal

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": "sencha"}'))
    ]

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=fake_openai),
        patch("app.routers.webhook.get_embedding_client", return_value=fake_openai),
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "777", "777", "I really love sencha the most", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    from app.db.models import Favourite

    user = db_session.query(User).filter_by(channel_id=channel_id, telegram_user_id="777").one()
    favourites = db_session.query(Favourite).filter_by(user_id=user.id).all()
    assert len(favourites) == 1
    assert favourites[0].drink_name == "sencha"


@pytest.mark.asyncio
async def test_process_message_background_summarization_actually_runs(db_session, channel_id):
    from tests.conftest import TestSessionLocal
    from app.db.models import ConversationSummary, Message

    user = User(channel_id=channel_id, telegram_user_id="888")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    for i in range(29):  # 29 existing + 1 from this turn = 30 -> 20 aged out, threshold met
        db_session.add(Message(user_id=user.id, role="user", content=f"msg {i}"))
    db_session.commit()

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Rolling summary of the conversation so far."))
    ]

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=fake_openai),
        patch("app.routers.webhook.get_embedding_client", return_value=fake_openai),
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "888", "888", "one more message", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    row = db_session.query(ConversationSummary).filter_by(user_id=user.id).one()
    assert row.summary_text == "Rolling summary of the conversation so far."


@pytest.mark.asyncio
async def test_process_message_background_customer_note_extraction_actually_runs(
    db_session, channel_id
):
    from tests.conftest import TestSessionLocal
    from app.db.models import CustomerNote

    user = User(channel_id=channel_id, telegram_user_id="999")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"allergy": "peanuts", "budget": None, "sugar_ice_level": None})
            )
        )
    ]

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=fake_openai),
        patch("app.routers.webhook.get_embedding_client", return_value=fake_openai),
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "999", "999", "I have a peanut allergy", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    row = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="allergy").one()
    assert row.value == "peanuts"


@pytest.mark.asyncio
async def test_process_message_background_recommendation_extraction_actually_runs(
    db_session, channel_id
):
    from app.db.models import RecommendationHistory
    from tests.conftest import TestSessionLocal

    user = User(channel_id=channel_id, telegram_user_id="998")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {"product_name": "hojicha", "reason": "ít caffeine, hợp buổi tối"}
                )
            )
        )
    ]

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=fake_openai),
        patch("app.routers.webhook.get_embedding_client", return_value=fake_openai),
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            # run_agent returns a *new* AgentState; mirror that so the test
            # covers the copy-back the webhook has to do for the extractors.
            return state.model_copy(
                update={
                    "reply": "Bạn nên thử hojicha, ít caffeine nên không lo mất ngủ.",
                    "retrieved_chunks": ["Hojicha là trà xanh rang, ít caffeine (10-20mg)."],
                }
            )

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "998", "998", "tôi hay mất ngủ thì uống gì được", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    row = db_session.query(RecommendationHistory).filter_by(user_id=user.id).one()
    assert row.product_name == "hojicha"
    assert row.reason == "ít caffeine, hợp buổi tối"


@pytest.mark.asyncio
async def test_process_message_background_favourite_extraction_records_error_metric_on_failure(
    db_session, channel_id
):
    from tests.conftest import TestSessionLocal

    user = User(channel_id=channel_id, telegram_user_id="997")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.extract_favourite", side_effect=RuntimeError("boom")),
        patch("app.routers.webhook.get_chat_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_embedding_client", return_value=MagicMock()),
        patch("app.routers.webhook.record_extraction") as mock_record,
        patch("app.db.base.SessionLocal", TestSessionLocal),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "997", "997", "hi", db_session
        )

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task

    mock_record.assert_called_once_with("favourite", "error")


def test_get_or_create_user_sets_last_active_at_for_a_new_user(db_session, channel_id):
    from datetime import UTC, datetime

    before = datetime.now(UTC).replace(tzinfo=None)
    user = _get_or_create_user(db_session, channel_id, "la-new")
    after = datetime.now(UTC).replace(tzinfo=None)

    # SQLite round-trips DateTime(timezone=True) as naive in this test
    # suite's in-memory engine — compare on naive values on both sides.
    assert user.last_active_at is not None
    assert before <= user.last_active_at.replace(tzinfo=None) <= after


def test_get_or_create_user_updates_last_active_at_for_an_existing_user(db_session, channel_id):
    from datetime import UTC, datetime, timedelta

    user = _get_or_create_user(db_session, channel_id, "la-existing")
    old_timestamp = (datetime.now(UTC) - timedelta(days=5)).replace(tzinfo=None)
    user.last_active_at = old_timestamp
    db_session.commit()

    user_again = _get_or_create_user(db_session, channel_id, "la-existing")

    assert user_again.id == user.id
    assert user_again.last_active_at.replace(tzinfo=None) > old_timestamp


@pytest.mark.asyncio
async def test_process_message_blocks_reply_when_daily_token_limit_reached(db_session, channel_id):
    from app import llm_settings
    from app.db.models import TokenUsage

    user = User(channel_id=channel_id, telegram_user_id="limit1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        TokenUsage(user_id=user.id, call_type="generate", model="gpt-4o-mini", prompt_tokens=1000, total_tokens=1000)
    )
    db_session.commit()
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="k",
        chat_model="gpt-4o-mini",
        updated_by="admin",
        daily_token_limit=1000,
    )

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock) as mock_send,
        patch("app.routers.webhook.record_daily_limit_hit") as mock_record_limit,
    ):
        await process_telegram_message(
            channel_id, "TEST_TOKEN", "limit1", "limit1", "one more question", db_session
        )

        mock_run_agent.assert_not_called()
        mock_send.assert_called_once()
        sent_text = mock_send.call_args.kwargs.get("text") or mock_send.call_args.args[-1]
        assert "limit" in sent_text.lower() or "giới hạn" in sent_text
        mock_record_limit.assert_called_once_with(channel_id)

    reply_row = (
        db_session.query(Message)
        .filter_by(user_id=user.id, role="assistant")
        .order_by(Message.id.desc())
        .first()
    )
    assert reply_row is not None


@pytest.mark.asyncio
async def test_process_message_proceeds_when_under_daily_token_limit(db_session, channel_id):
    from app import llm_settings

    user = User(channel_id=channel_id, telegram_user_id="limit2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    llm_settings.save(
        db_session,
        provider="openai",
        base_url=None,
        api_key="k",
        chat_model="gpt-4o-mini",
        updated_by="admin",
        daily_token_limit=1000,
    )

    with (
        patch("app.routers.webhook.run_agent") as mock_run_agent,
        patch("app.routers.webhook.send_message", new_callable=AsyncMock),
        patch("app.routers.webhook.edit_message_text", new_callable=AsyncMock),
        patch("app.routers.webhook.send_chat_action", new_callable=AsyncMock),
        patch("app.routers.webhook.get_chat_client", return_value=MagicMock()),
        patch("app.routers.webhook.get_embedding_client", return_value=MagicMock()),
    ):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        await process_telegram_message(
            channel_id, "TEST_TOKEN", "limit2", "limit2", "a question", db_session
        )

        mock_run_agent.assert_called_once()

        from app.routers.webhook import _background_tasks

        for task in list(_background_tasks):
            await task
