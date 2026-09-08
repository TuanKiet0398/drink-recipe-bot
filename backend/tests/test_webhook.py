import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import User
from app.routers.webhook import THINKING_PLACEHOLDER, process_telegram_message


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
