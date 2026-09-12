import json
from unittest.mock import AsyncMock, patch

from app.crypto import decrypt, encrypt
from app.db.models import Channel


def test_create_channel_requires_auth(client):
    response = client.post(
        "/admin/channels",
        json={"key": "a", "display_name": "A", "channel_type": "telegram", "bot_token": "t"},
    )
    assert response.status_code == 401


def test_create_channel_encrypts_the_token_and_never_returns_it(client, db_session):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.post(
            "/admin/channels",
            json={
                "key": "my-bot",
                "display_name": "My Bot",
                "channel_type": "telegram",
                "bot_token": "secret-token",
            },
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "my-bot"
    assert "bot_token" not in body
    assert "encrypted_credentials" not in body

    channel = db_session.query(Channel).filter_by(key="my-bot").one()
    assert channel.encrypted_credentials != "secret-token"
    assert json.loads(decrypt(channel.encrypted_credentials))["bot_token"] == "secret-token"
    mock_sync.assert_awaited_once()


def test_create_channel_rejects_unsupported_channel_type(client, db_session):
    response = client.post(
        "/admin/channels",
        json={"key": "zalo-bot", "display_name": "Zalo", "channel_type": "zalo", "bot_token": "t"},
        auth=("admin", "admin"),
    )
    assert response.status_code == 400
    assert db_session.query(Channel).count() == 0


def test_list_channels_never_includes_credentials(client, db_session, channel_id):
    response = client.get("/admin/channels", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "encrypted_credentials" not in body[0]
    assert "bot_token" not in body[0]
    assert body[0]["id"] == channel_id


def test_update_channel_toggles_active_and_syncs(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.patch(
            f"/admin/channels/{channel_id}", json={"is_active": False}, auth=("admin", "admin")
        )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    mock_sync.assert_awaited_once()


def test_update_channel_can_rotate_the_bot_token(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        client.patch(
            f"/admin/channels/{channel_id}", json={"bot_token": "new-token"}, auth=("admin", "admin")
        )

    channel = db_session.query(Channel).filter_by(id=channel_id).one()
    assert json.loads(decrypt(channel.encrypted_credentials))["bot_token"] == "new-token"


def test_delete_channel_soft_deletes_it_and_syncs(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))

    assert response.status_code == 204
    channel = db_session.query(Channel).filter_by(id=channel_id).one()
    assert channel.deleted_at is not None
    assert channel.is_active is False
    mock_sync.assert_awaited_once()


def test_list_channels_hides_soft_deleted_ones(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))

    response = client.get("/admin/channels", auth=("admin", "admin"))
    assert response.status_code == 200
    assert response.json() == []


def test_delete_channel_keeps_its_users_and_their_memory(client, db_session, channel_id):
    """Deleting a channel must not erase the customers behind it — re-adding
    the same bot revives the channel, and their memory has to still be there."""
    from app.db.models import RecommendationHistory, User

    user = User(channel_id=channel_id, telegram_user_id="123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(RecommendationHistory(user_id=user.id, product_name="matcha", reason="r"))
    db_session.commit()

    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        response = client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(User).filter_by(id=user.id).count() == 1
    assert db_session.query(RecommendationHistory).filter_by(user_id=user.id).count() == 1


def test_recreating_a_channel_with_the_same_bot_token_revives_the_old_one(client, db_session):
    """Same bot token = same channel row, so the users hanging off that
    channel_id (and everything they told the bot) survive a delete/re-add."""
    from app.db.models import User

    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        created = client.post(
            "/admin/channels",
            json={
                "key": "shop-bot",
                "display_name": "Shop Bot",
                "channel_type": "telegram",
                "bot_token": "the-same-token",
            },
            auth=("admin", "admin"),
        ).json()

        user = User(channel_id=created["id"], telegram_user_id="555")
        db_session.add(user)
        db_session.commit()

        client.delete(f"/admin/channels/{created['id']}", auth=("admin", "admin"))

        revived = client.post(
            "/admin/channels",
            json={
                "key": "shop-bot-again",
                "display_name": "Shop Bot Again",
                "channel_type": "telegram",
                "bot_token": "the-same-token",
            },
            auth=("admin", "admin"),
        )

    assert revived.status_code == 201
    body = revived.json()
    assert body["id"] == created["id"]
    assert body["display_name"] == "Shop Bot Again"
    assert body["is_active"] is True
    assert db_session.query(Channel).count() == 1
    assert db_session.query(User).filter_by(channel_id=created["id"]).count() == 1


def test_recreating_a_channel_with_a_different_token_creates_a_new_row(client, db_session):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        first = client.post(
            "/admin/channels",
            json={"key": "a", "display_name": "A", "channel_type": "telegram", "bot_token": "token-a"},
            auth=("admin", "admin"),
        ).json()
        second = client.post(
            "/admin/channels",
            json={"key": "b", "display_name": "B", "channel_type": "telegram", "bot_token": "token-b"},
            auth=("admin", "admin"),
        ).json()

    assert first["id"] != second["id"]
    assert db_session.query(Channel).count() == 2


def test_update_channel_on_a_soft_deleted_channel_returns_404(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))
        response = client.patch(
            f"/admin/channels/{channel_id}", json={"is_active": True}, auth=("admin", "admin")
        )

    assert response.status_code == 404


def test_force_delete_channel_erases_users_and_every_memory_table(client, db_session, channel_id):
    from app.db.models import (
        ConversationSummary,
        CustomerNote,
        Favourite,
        Message,
        RecommendationHistory,
        TokenUsage,
        User,
    )

    user = User(channel_id=channel_id, telegram_user_id="123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    user_id = user.id
    db_session.add(Message(user_id=user_id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user_id, drink_name="matcha"))
    db_session.add(CustomerNote(user_id=user_id, note_type="allergy", value="dairy"))
    db_session.add(ConversationSummary(user_id=user_id, summary_text="prefers oat milk"))
    db_session.add(RecommendationHistory(user_id=user_id, product_name="hojicha", reason="r"))
    db_session.add(
        TokenUsage(
            user_id=user_id, call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1
        )
    )
    db_session.commit()

    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.delete(f"/admin/channels/{channel_id}?force=true", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Channel).filter_by(id=channel_id).count() == 0
    assert db_session.query(User).filter_by(id=user_id).count() == 0
    assert db_session.query(Message).filter_by(user_id=user_id).count() == 0
    assert db_session.query(Favourite).filter_by(user_id=user_id).count() == 0
    assert db_session.query(TokenUsage).filter_by(user_id=user_id).count() == 0
    # These three were silently left behind before, so a reused user id would
    # inherit a stranger's allergy note, summary and recommendations.
    assert db_session.query(CustomerNote).filter_by(user_id=user_id).count() == 0
    assert db_session.query(ConversationSummary).filter_by(user_id=user_id).count() == 0
    assert db_session.query(RecommendationHistory).filter_by(user_id=user_id).count() == 0
    mock_sync.assert_awaited_once()


def test_test_connection_with_a_typed_token_requires_auth(client):
    response = client.post("/admin/channels/test", json={"channel_type": "telegram", "bot_token": "t"})
    assert response.status_code == 401


def test_test_connection_with_a_typed_valid_token(client, db_session):
    with patch("app.routers.admin_channels.get_me", new_callable=AsyncMock) as mock_get_me:
        mock_get_me.return_value = {"username": "my_shop_bot"}
        response = client.post(
            "/admin/channels/test",
            json={"channel_type": "telegram", "bot_token": "good-token"},
            auth=("admin", "admin"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "username": "my_shop_bot"}
    mock_get_me.assert_awaited_once_with("good-token")


def test_test_connection_with_a_typed_invalid_token(client, db_session):
    with patch("app.routers.admin_channels.get_me", new_callable=AsyncMock) as mock_get_me:
        mock_get_me.side_effect = ValueError("Unauthorized")
        response = client.post(
            "/admin/channels/test",
            json={"channel_type": "telegram", "bot_token": "bad-token"},
            auth=("admin", "admin"),
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unauthorized"


def test_test_connection_rejects_unsupported_channel_type(client, db_session):
    response = client.post(
        "/admin/channels/test",
        json={"channel_type": "zalo", "bot_token": "t"},
        auth=("admin", "admin"),
    )
    assert response.status_code == 400


def test_test_existing_channel_connection_uses_stored_token(client, db_session):
    channel = Channel(
        key="bot-a",
        display_name="Bot A",
        channel_type="telegram",
        encrypted_credentials=encrypt(json.dumps({"bot_token": "stored-token"})),
        is_active=True,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)

    with patch("app.routers.admin_channels.get_me", new_callable=AsyncMock) as mock_get_me:
        mock_get_me.return_value = {"username": "my_shop_bot"}
        response = client.post(f"/admin/channels/{channel.id}/test", auth=("admin", "admin"))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "username": "my_shop_bot"}
    mock_get_me.assert_awaited_once_with("stored-token")


def test_test_existing_channel_connection_returns_404_when_missing(client, db_session):
    response = client.post("/admin/channels/999/test", auth=("admin", "admin"))
    assert response.status_code == 404
