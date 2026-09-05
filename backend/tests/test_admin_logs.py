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


def test_delete_audit_log_entry_requires_auth(client, db_session):
    entry = AdminAuditLog(action="login")
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    assert client.delete(f"/admin/logs/audit/{entry.id}").status_code == 401


def test_delete_audit_log_entry(client, db_session):
    entry = AdminAuditLog(action="login")
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    response = client.delete(f"/admin/logs/audit/{entry.id}", auth=("admin", "admin"))
    assert response.status_code == 204
    # Not asserting on id=entry.id: SQLite reuses a deleted rowid for the
    # next insert once the table is empty, and the delete's own audit
    # entry (logged right after) would otherwise collide with it.
    assert db_session.query(AdminAuditLog).filter_by(action="login").count() == 0


def test_delete_audit_log_entry_returns_404_when_missing(client, db_session):
    response = client.delete("/admin/logs/audit/999", auth=("admin", "admin"))
    assert response.status_code == 404


def test_audit_log_filters_by_action(client, db_session):
    db_session.add(AdminAuditLog(action="login"))
    db_session.add(AdminAuditLog(action="login_failed"))
    db_session.add(AdminAuditLog(action="login_failed"))
    db_session.commit()

    response = client.get("/admin/logs/audit?action=login_failed", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all(row["action"] == "login_failed" for row in body)


def test_audit_log_searches_target_and_ip(client, db_session):
    db_session.add(AdminAuditLog(action="login_failed", target="alice", ip="10.0.0.1"))
    db_session.add(AdminAuditLog(action="login_failed", target="bob", ip="10.0.0.2"))
    db_session.add(AdminAuditLog(action="delete_doc", target="menu.txt", ip="10.0.0.1"))
    db_session.commit()

    by_target = client.get("/admin/logs/audit?q=alice", auth=("admin", "admin")).json()
    assert len(by_target) == 1
    assert by_target[0]["target"] == "alice"

    by_ip = client.get("/admin/logs/audit?q=10.0.0.1", auth=("admin", "admin")).json()
    assert len(by_ip) == 2

    case_insensitive = client.get("/admin/logs/audit?q=ALICE", auth=("admin", "admin")).json()
    assert len(case_insensitive) == 1


def test_audit_log_actions_lists_distinct_values(client, db_session):
    db_session.add(AdminAuditLog(action="login"))
    db_session.add(AdminAuditLog(action="login"))
    db_session.add(AdminAuditLog(action="delete_doc"))
    db_session.commit()

    response = client.get("/admin/logs/audit/actions", auth=("admin", "admin"))
    assert response.status_code == 200
    assert sorted(response.json()) == ["delete_doc", "login"]


def test_audit_log_actions_requires_auth(client):
    assert client.get("/admin/logs/audit/actions").status_code == 401


def test_clear_audit_log(client, db_session):
    db_session.add(AdminAuditLog(action="login"))
    db_session.add(AdminAuditLog(action="logout"))
    db_session.commit()

    response = client.delete("/admin/logs/audit", auth=("admin", "admin"))
    assert response.status_code == 204
    # The clear action's own audit entry is written after the delete, so
    # exactly one row (that entry) should remain.
    remaining = db_session.query(AdminAuditLog).all()
    assert len(remaining) == 1
    assert remaining[0].action == "clear_audit_log"
