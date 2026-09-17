from app.db.models import (
    AdminAuditLog,
    ConversationSummary,
    CustomerNote,
    Favourite,
    Message,
    RecommendationHistory,
    TokenUsage,
    User,
)


def test_list_users_requires_auth(client):
    assert client.get("/admin/users").status_code == 401


def test_list_users_returns_summary(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="1")
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
    assert body[0]["channel_id"] == channel_id
    assert body[0]["message_count"] == 1
    assert body[0]["favourites"] == ["matcha"]
    assert body[0]["blocked"] is False


def test_block_and_unblock_user(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="2")
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


def test_block_user_writes_audit_log(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="4")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client.post(f"/admin/users/{user.id}/block", auth=("admin", "admin"))

    logs = db_session.query(AdminAuditLog).filter_by(action="block_user").all()
    assert len(logs) == 1
    assert logs[0].target == "4"


def test_delete_user_requires_auth(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="del-1")
    db_session.add(user)
    db_session.commit()

    assert client.delete(f"/admin/users/{user.id}").status_code == 401


def test_delete_user_returns_404_for_unknown_id(client):
    assert client.delete("/admin/users/999999", auth=("admin", "admin")).status_code == 404


def test_delete_user_erases_the_user_and_all_their_memory(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="del-2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    user_id = user.id

    db_session.add(Message(user_id=user_id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user_id, drink_name="matcha"))
    db_session.add(TokenUsage(user_id=user_id, call_type="generate", model="gpt-4o-mini", prompt_tokens=10, completion_tokens=5, total_tokens=15))
    db_session.add(CustomerNote(user_id=user_id, note_type="allergy", value="hạt"))
    db_session.add(ConversationSummary(user_id=user_id, summary_text="test summary"))
    db_session.add(RecommendationHistory(user_id=user_id, product_name="matcha latte"))
    db_session.commit()

    response = client.delete(f"/admin/users/{user_id}", auth=("admin", "admin"))
    assert response.status_code == 204

    assert db_session.query(User).filter_by(id=user_id).one_or_none() is None
    assert db_session.query(Message).filter_by(user_id=user_id).count() == 0
    assert db_session.query(Favourite).filter_by(user_id=user_id).count() == 0
    assert db_session.query(TokenUsage).filter_by(user_id=user_id).count() == 0
    assert db_session.query(CustomerNote).filter_by(user_id=user_id).count() == 0
    assert db_session.query(ConversationSummary).filter_by(user_id=user_id).count() == 0
    assert db_session.query(RecommendationHistory).filter_by(user_id=user_id).count() == 0


def test_delete_user_does_not_affect_other_users(client, db_session, channel_id):
    keep = User(channel_id=channel_id, telegram_user_id="keep-me")
    remove = User(channel_id=channel_id, telegram_user_id="remove-me")
    db_session.add_all([keep, remove])
    db_session.commit()
    db_session.refresh(keep)
    db_session.refresh(remove)
    db_session.add(Favourite(user_id=keep.id, drink_name="hojicha"))
    db_session.commit()

    response = client.delete(f"/admin/users/{remove.id}", auth=("admin", "admin"))
    assert response.status_code == 204

    assert db_session.query(User).filter_by(id=keep.id).one_or_none() is not None
    assert db_session.query(Favourite).filter_by(user_id=keep.id).count() == 1


def test_delete_user_writes_audit_log(client, db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="del-3")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client.delete(f"/admin/users/{user.id}", auth=("admin", "admin"))

    logs = db_session.query(AdminAuditLog).filter_by(action="delete_user").all()
    assert len(logs) == 1
    assert logs[0].target == "del-3"


def test_login_with_valid_credentials_writes_audit_log(client, db_session):
    response = client.post("/admin/login", auth=("admin", "admin"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "role": "admin"}

    logs = db_session.query(AdminAuditLog).filter_by(action="login").all()
    assert len(logs) == 1
    assert logs[0].target == "admin"


def test_login_with_bad_credentials_returns_401_and_logs_failed_attempt(client, db_session):
    response = client.post("/admin/login", auth=("admin", "wrong-password"))

    assert response.status_code == 401
    assert db_session.query(AdminAuditLog).filter_by(action="login").count() == 0
    failed = db_session.query(AdminAuditLog).filter_by(action="login_failed").all()
    assert len(failed) == 1
    assert failed[0].target == "admin"
