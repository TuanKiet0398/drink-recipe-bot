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

    stream_chunk = MagicMock()
    stream_chunk.choices = [MagicMock(delta=MagicMock(content="Try ceremonial grade!"))]
    stream_chunk.usage = None
    final_chunk = MagicMock()
    final_chunk.choices = []
    final_chunk.usage = None
    fake_openai.chat.completions.create.return_value = [stream_chunk, final_chunk]

    fake_qdrant = MagicMock()
    fake_qdrant.query_points.return_value = MagicMock(points=[])

    seen: list[str] = []
    result = run_agent(state, db=db_session, qdrant_client=fake_qdrant, openai_client=fake_openai, on_delta=seen.append)

    assert result.reply == "Try ceremonial grade!"
    assert seen == ["Try ceremonial grade!"]
