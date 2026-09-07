from unittest.mock import MagicMock

from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.db.models import User


def test_run_agent_produces_a_reply(db_session, channel_id):
    user = User(channel_id=channel_id, telegram_user_id="55")
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


def test_graph_nodes_record_duration(db_session, monkeypatch):
    from prometheus_client import REGISTRY

    from app.agent import graph as graph_module
    from app.agent.state import AgentState

    def _fake_node(state, *args, **kwargs):
        return state

    monkeypatch.setattr(graph_module, "fetch_history", _fake_node)
    monkeypatch.setattr(graph_module, "retrieve", _fake_node)
    monkeypatch.setattr(graph_module, "generate", _fake_node)

    labels = {"node": "retrieve"}
    before = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0

    graph_module.run_agent(
        AgentState(user_id=1, chat_id="1", incoming_text="hi"),
        db=db_session,
        chroma_client=None,
        openai_client=None,
    )

    after = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0
    assert after - before == 1


def test_timed_wrapper_records_duration_even_when_the_node_raises():
    from prometheus_client import REGISTRY

    from app.agent.graph import _timed

    labels = {"node": "exploding"}
    before = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0

    def _boom(state):
        raise RuntimeError("node failed")

    wrapped = _timed("exploding", _boom)
    try:
        wrapped({})
    except RuntimeError:
        pass

    after = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0
    assert after - before == 1
