from app.db.models import User, Message, Favourite, Document, AdminAuditLog


def test_create_user_with_related_rows(db_session):
    user = User(telegram_user_id="123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Favourite(user_id=user.id, drink_name="genmaicha"))
    db_session.add(Document(filename="brewing.pdf", chunk_count=5))
    db_session.add(AdminAuditLog(action="login"))
    db_session.commit()

    assert db_session.query(Message).count() == 1
    assert db_session.query(Favourite).count() == 1
    assert db_session.query(Document).count() == 1
    assert db_session.query(AdminAuditLog).count() == 1
    assert user.blocked is False
