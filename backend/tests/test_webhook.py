from unittest.mock import AsyncMock, patch

from app.db.models import User


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
    ) as mock_send, patch("app.routers.webhook.extract_favourite"):
        from app.agent.state import AgentState

        def fake_run_agent(state, **kwargs):
            state.reply = "Welcome!"
            return state

        mock_run_agent.side_effect = fake_run_agent

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_send.assert_awaited_once()
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
