from typing import Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import fetch_history, generate, retrieve
from app.agent.state import AgentState


def build_graph(db: Session, chroma_client, openai_client, on_delta: Callable[[str], None] | None = None):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", lambda s: fetch_history(s, db))
    graph.add_node("retrieve", lambda s: retrieve(s, db, chroma_client, openai_client))
    graph.add_node("generate", lambda s: generate(s, db, openai_client, on_delta=on_delta))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(
    state: AgentState,
    db: Session,
    chroma_client,
    openai_client,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    compiled = build_graph(db, chroma_client, openai_client, on_delta=on_delta)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
