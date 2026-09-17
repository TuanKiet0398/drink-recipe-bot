from collections.abc import Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import check_facts, fetch_history, generate, retrieve
from app.agent.state import AgentState
from app.metrics import AGENT_NODE_DURATION


def _timed(node_name: str, fn: Callable) -> Callable:
    """Wrap a graph node so its wall time lands in Prometheus.

    `Histogram.time()` observes on context exit, including when the node
    raises — a slow failure is exactly the case worth seeing.
    """

    def _wrapped(state):
        with AGENT_NODE_DURATION.labels(node=node_name).time():
            return fn(state)

    return _wrapped


def build_graph(
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    on_delta: Callable[[str], None] | None = None,
):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", _timed("fetch_history", lambda s: fetch_history(s, db)))
    graph.add_node(
        "retrieve",
        _timed(
            "retrieve",
            lambda s: retrieve(s, db, chroma_client, chat_client, embedding_client, chat_model),
        ),
    )
    graph.add_node(
        "generate",
        _timed("generate", lambda s: generate(s, db, chat_client, chat_model, on_delta=on_delta)),
    )
    graph.add_node("check_facts", _timed("check_facts", check_facts))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "check_facts")
    graph.add_edge("check_facts", END)

    return graph.compile()


def run_agent(
    state: AgentState,
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    compiled = build_graph(db, chroma_client, chat_client, embedding_client, chat_model, on_delta=on_delta)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
