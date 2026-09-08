import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    AdminAuditLog,
    Channel,
    ConversationSummary,
    CustomerNote,
    Document,
    Favourite,
    Message,
    User,
)


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


def test_conversation_summary_one_row_per_user(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="c1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(ConversationSummary(user_id=user.id, summary_text="likes hojicha, avoid dairy"))
    db_session.commit()

    row = db_session.query(ConversationSummary).filter_by(user_id=user.id).one()
    assert row.summary_text == "likes hojicha, avoid dairy"
    assert row.last_summarized_message_id is None
    assert row.updated_at is not None


def test_customer_note_unique_per_user_and_type(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(CustomerNote(user_id=user.id, note_type="allergy", value="dairy"))
    db_session.commit()

    row = db_session.query(CustomerNote).filter_by(user_id=user.id, note_type="allergy").one()
    assert row.value == "dairy"
    assert row.confidence == "inferred"
    assert row.source == "chat"
    assert row.updated_at is not None


def test_customer_note_rejects_a_second_row_for_the_same_user_and_type(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="cn2")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="50k"))
    db_session.commit()

    db_session.add(CustomerNote(user_id=user.id, note_type="budget", value="60k"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_last_active_at_defaults_to_none(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="la1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.last_active_at is None


def test_user_last_active_at_can_be_set(db_session, channel_id):
    from datetime import UTC, datetime

    user = User(channel_id=channel_id, telegram_user_id="la2")
    db_session.add(user)
    db_session.commit()

    now = datetime.now(UTC)
    user.last_active_at = now
    db_session.commit()
    db_session.refresh(user)

    assert user.last_active_at is not None
