from app.db.models import AdminAuditLog, Favourite, Message, User


def test_list_users_requires_auth(client):
    assert client.get("/admin/users").status_code == 401


def test_list_users_returns_summary(client, db_session):
    user = User(telegram_user_id="1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user.id, drink_name="matcha"))
    db_session.commit()

    response = client.get("/admin/users", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["telegram_user_id"] == "1"
    assert body[0]["message_count"] == 1
    assert body[0]["favourites"] == ["matcha"]
    assert body[0]["blocked"] is False


def test_block_and_unblock_user(client, db_session):
    user = User(telegram_user_id="2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    block_response = client.post(f"/admin/users/{user.id}/block", auth=("admin", "admin"))
    assert block_response.status_code == 200
    db_session.refresh(user)
    assert user.blocked is True

    unblock_response = client.post(f"/admin/users/{user.id}/unblock", auth=("admin", "admin"))
    assert unblock_response.status_code == 200
    db_session.refresh(user)
    assert user.blocked is False


def test_block_user_writes_audit_log(client, db_session):
    user = User(telegram_user_id="4")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client.post(f"/admin/users/{user.id}/block", auth=("admin", "admin"))

    logs = db_session.query(AdminAuditLog).filter_by(action="block_user").all()
    assert len(logs) == 1
    assert logs[0].target == "4"
