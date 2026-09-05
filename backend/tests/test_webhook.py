import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import AdminAuditLog, User


def test_webhook_creates_user_stores_message_and_replies(client, db_session):
    payload = {
        "message": {
            "chat": {"id": 111},
            "from": {"id": 111},
            "text": "hi there",
        }
    }

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ) as mock_typing, patch("app.routers.webhook.extract_favourite"), patch(
        # get_qdrant_client()/get_openai_client() are evaluated as argument
        # expressions to run_agent() even though run_agent is mocked below —
        # stub them out too so their real (env-dependent) construction
        # doesn't get exercised in this unit test.
        "app.routers.webhook.get_qdrant_client",
        return_value=MagicMock(),
    ), patch("app.routers.webhook.get_openai_client", return_value=MagicMock()):
        from app.agent.state import AgentState

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_send.assert_awaited_once()
    assert mock_send.call_args.kwargs["text"] == "Welcome!"
    mock_typing.assert_awaited_once_with(chat_id="111", action="typing")
    user = db_session.query(User).filter_by(telegram_user_id="111").one()
    assert user is not None


def test_webhook_skips_blocked_user(client, db_session):
    from app.db.models import User as UserModel

    blocked = UserModel(telegram_user_id="222", blocked=True)
    db_session.add(blocked)
    db_session.commit()

    payload = {"message": {"chat": {"id": 222}, "from": {"id": 222}, "text": "hello"}}

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send:
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_run_agent.assert_not_called()
    mock_send.assert_not_awaited()


def test_webhook_returns_200_even_when_send_message_fails(client, db_session):
    payload = {
        "message": {
            "chat": {"id": 333},
            "from": {"id": 333},
            "text": "hi there",
        }
    }

    with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch("app.routers.webhook.extract_favourite"):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent
        mock_send.side_effect = RuntimeError("Telegram API error")

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_send.assert_awaited_once()
    user = db_session.query(User).filter_by(telegram_user_id="333").one()
    assert user is not None


def _fake_settings(secret: str = "") -> MagicMock:
    settings = MagicMock()
    settings.telegram_webhook_secret = secret
    return settings


def test_webhook_rejects_missing_secret_header_when_configured(client, db_session):
    payload = {"message": {"chat": {"id": 444}, "from": {"id": 444}, "text": "hi"}}

    with patch("app.routers.webhook.get_settings", return_value=_fake_settings("s3cr3t")):
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 401
    assert db_session.query(User).filter_by(telegram_user_id="444").one_or_none() is None


def test_webhook_rejects_wrong_secret_header_when_configured(client, db_session):
    payload = {"message": {"chat": {"id": 444}, "from": {"id": 444}, "text": "hi"}}

    with patch("app.routers.webhook.get_settings", return_value=_fake_settings("s3cr3t")):
        response = client.post(
            "/webhook/telegram",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )

    assert response.status_code == 401


def test_webhook_accepts_correct_secret_header(client, db_session):
    payload = {"message": {"chat": {"id": 555}, "from": {"id": 555}, "text": "hi there"}}

    with patch("app.routers.webhook.get_settings", return_value=_fake_settings("s3cr3t")), patch(
        "app.routers.webhook.run_agent"
    ) as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch("app.routers.webhook.extract_favourite"):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        response = client.post(
            "/webhook/telegram",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
        )

    assert response.status_code == 200
    mock_send.assert_awaited_once()


def test_webhook_proceeds_when_no_secret_configured(client, db_session):
    payload = {"message": {"chat": {"id": 666}, "from": {"id": 666}, "text": "hi there"}}

    with patch("app.routers.webhook.get_settings", return_value=_fake_settings("")), patch(
        "app.routers.webhook.run_agent"
    ) as mock_run_agent, patch(
        "app.routers.webhook.send_message", new_callable=AsyncMock
    ) as mock_send, patch(
        "app.routers.webhook.send_chat_action", new_callable=AsyncMock
    ), patch("app.routers.webhook.extract_favourite"):

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_send.assert_awaited_once()


async def test_webhook_background_favourite_extraction_actually_runs(db_session):
    import httpx

    from app.main import app
    from app.db.base import get_db
    from tests.conftest import TestSessionLocal

    payload = {
        "message": {
            "chat": {"id": 777},
            "from": {"id": 777},
            "text": "I really love sencha the most",
        }
    }

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"drink_name": "sencha"}'))
    ]

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    try:
        with patch("app.routers.webhook.run_agent") as mock_run_agent, patch(
            "app.routers.webhook.send_message", new_callable=AsyncMock
        ), patch(
            "app.routers.webhook.send_chat_action", new_callable=AsyncMock
        ), patch(
            "app.routers.webhook.get_openai_client", return_value=fake_openai
        ), patch(
            # The background task opens its own SessionLocal() rather than
            # using the request-scoped `db` fixture override — point it at
            # the same in-memory test database so the write is observable.
            "app.db.base.SessionLocal",
            TestSessionLocal,
        ):

            def fake_run_agent(state, **kwargs):
                state.reply = "Welcome!"
                return state

            mock_run_agent.side_effect = fake_run_agent

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
                response = await async_client.post("/webhook/telegram", json=payload)
                assert response.status_code == 200

                from app.routers.webhook import _background_tasks

                # Wait on the tracked background task set directly instead
                # of guessing how many event-loop turns it needs.
                for task in list(_background_tasks):
                    await task
    finally:
        app.dependency_overrides.clear()

    from app.db.models import Favourite

    user = db_session.query(User).filter_by(telegram_user_id="777").one()
    favourites = db_session.query(Favourite).filter_by(user_id=user.id).all()
    assert len(favourites) == 1
    assert favourites[0].drink_name == "sencha"
