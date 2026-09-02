from app.agent.nodes import fetch_history
from app.agent.state import AgentState
from app.db.models import User, Message, Favourite


def test_fetch_history_loads_recent_messages_and_favourites(db_session):
    user = User(telegram_user_id="99")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(Message(user_id=user.id, role="user", content="hi"))
    db_session.add(Message(user_id=user.id, role="assistant", content="hello!"))
    db_session.add(Favourite(user_id=user.id, drink_name="hojicha"))
    db_session.commit()

    state = AgentState(user_id=user.id, chat_id="99", incoming_text="what do you recommend?")
    result = fetch_history(state, db_session)

    assert len(result.history) == 2
    assert result.history[0]["content"] == "hi"
    assert result.favourites == ["hojicha"]
