from app.db.models import AdminAuditLog, Message, User


def test_access_log_requires_auth(client):
    assert client.get("/admin/logs/access").status_code == 401


def test_access_log_returns_messages(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="3")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    response = client.get("/admin/logs/access", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["content"] == "hi"
    assert body[0]["telegram_user_id"] == "3"


def test_audit_log_returns_actions(client, db_session):
    db_session.add(AdminAuditLog(action="login"))
    db_session.commit()

    response = client.get("/admin/logs/audit", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body[0]["action"] == "login"


def test_logs_respect_limit_and_offset(client, db_session):
    for i in range(3):
        db_session.add(AdminAuditLog(action=f"action-{i}"))
    db_session.commit()

    response = client.get("/admin/logs/audit?limit=1&offset=1", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1
