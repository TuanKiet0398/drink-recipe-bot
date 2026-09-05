import json
from unittest.mock import AsyncMock, patch

from app.crypto import decrypt, encrypt
from app.db.models import Channel


def test_create_channel_requires_auth(client):
    response = client.post("/admin/channels", json={"key": "a", "display_name": "A", "channel_type": "telegram", "bot_token": "t"})
    assert response.status_code == 401


def test_create_channel_encrypts_the_token_and_never_returns_it(client, db_session):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.post(
            "/admin/channels",
            json={"key": "my-bot", "display_name": "My Bot", "channel_type": "telegram", "bot_token": "secret-token"},
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
        response = client.patch(f"/admin/channels/{channel_id}", json={"is_active": False}, auth=("admin", "admin"))

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    mock_sync.assert_awaited_once()


def test_update_channel_can_rotate_the_bot_token(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock):
        client.patch(f"/admin/channels/{channel_id}", json={"bot_token": "new-token"}, auth=("admin", "admin"))

    channel = db_session.query(Channel).filter_by(id=channel_id).one()
    assert json.loads(decrypt(channel.encrypted_credentials))["bot_token"] == "new-token"


def test_delete_channel_removes_it_and_syncs(client, db_session, channel_id):
    with patch("app.routers.admin_channels.channel_manager.sync", new_callable=AsyncMock) as mock_sync:
        response = client.delete(f"/admin/channels/{channel_id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Channel).count() == 0
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
