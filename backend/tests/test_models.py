import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import AdminAuditLog, Channel, Document, Favourite, Message, User


def test_create_user_with_related_rows(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="123")
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


def test_users_unique_per_channel_and_telegram_id(db_session, channel_id):
    db_session.add(User(channel_id=channel_id, telegram_user_id="dup"))
    db_session.commit()

    other_channel = Channel(
        key="other-channel",
        display_name="Other",
        channel_type="telegram",
        encrypted_credentials="x",
    )
    db_session.add(other_channel)
    db_session.commit()
    db_session.refresh(other_channel)

    # Same telegram_user_id under a *different* channel is allowed.
    db_session.add(User(channel_id=other_channel.id, telegram_user_id="dup"))
    db_session.commit()

    # Same telegram_user_id under the *same* channel is not.
    db_session.add(User(channel_id=channel_id, telegram_user_id="dup"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
