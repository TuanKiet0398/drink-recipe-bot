from datetime import UTC, datetime, timedelta

from app.db.models import ConversationSummary, CustomerNote, Message, User
from app.retention import purge_inactive_messages


def _user_with_last_active(db_session, channel_id, telegram_user_id, days_ago):
    user = User(
        channel_id=channel_id,
        telegram_user_id=telegram_user_id,
        last_active_at=datetime.now(UTC) - timedelta(days=days_ago) if days_ago is not None else None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_purge_keeps_messages_for_a_recently_active_user(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p1", days_ago=5)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1


def test_purge_deletes_messages_for_a_user_inactive_over_30_days(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p2", days_ago=31)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Message(user_id=user.id, role="assistant", content="hello"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 2
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 0


def test_purge_keeps_summary_and_notes_for_a_purged_user(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p3", days_ago=45)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(ConversationSummary(user_id=user.id, summary_text="likes hojicha"))
    db_session.add(CustomerNote(user_id=user.id, note_type="allergy", value="dairy"))
    db_session.commit()

    purge_inactive_messages(db_session, inactive_days=30)

    assert db_session.query(Message).filter_by(user_id=user.id).count() == 0
    assert db_session.query(ConversationSummary).filter_by(user_id=user.id).count() == 1
    assert db_session.query(CustomerNote).filter_by(user_id=user.id).count() == 1
    assert db_session.query(User).filter_by(id=user.id).count() == 1


def test_purge_does_not_delete_just_inside_the_boundary(db_session, channel_id):
    # Just under 30 days inactive — a few minutes of margin so this isn't
    # racing the wall clock against purge_inactive_messages' own
    # datetime.now() call.
    user = User(
        channel_id=channel_id,
        telegram_user_id="p4",
        last_active_at=datetime.now(UTC) - timedelta(days=30) + timedelta(minutes=5),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1


def test_purge_ignores_users_with_no_last_active_at(db_session, channel_id):
    user = _user_with_last_active(db_session, channel_id, "p5", days_ago=None)
    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.commit()

    deleted = purge_inactive_messages(db_session, inactive_days=30)

    assert deleted == 0
    assert db_session.query(Message).filter_by(user_id=user.id).count() == 1
