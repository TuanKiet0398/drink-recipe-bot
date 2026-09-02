from unittest.mock import MagicMock

from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.db.models import User


def test_run_agent_produces_a_reply(db_session):
    user = User(telegram_user_id="55")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    state = AgentState(user_id=user.id, chat_id="55", incoming_text="recommend a matcha")

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Try ceremonial grade!"))
    ]

    fake_qdrant = MagicMock()
    fake_qdrant.search.return_value = []

    result = run_agent(state, db=db_session, qdrant_client=fake_qdrant, openai_client=fake_openai)

    assert result.reply == "Try ceremonial grade!"
