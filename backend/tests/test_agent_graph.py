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
    fake_openai.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="recommend a matcha"))], usage=None),  # rewrite_query
        [stream_chunk, final_chunk],  # generate()'s stream
    ]

    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [[]], "distances": [[]]}
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    seen: list[str] = []
    result = run_agent(state, db=db_session, chroma_client=fake_chroma, openai_client=fake_openai, on_delta=seen.append)

    assert result.reply == "Try ceremonial grade!"
    assert seen == ["Try ceremonial grade!"]
