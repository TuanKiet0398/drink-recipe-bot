from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import fetch_history, generate, retrieve
from app.agent.state import AgentState


def build_graph(db: Session, qdrant_client, openai_client):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", lambda s: fetch_history(s, db))
    graph.add_node("retrieve", lambda s: retrieve(s, qdrant_client, openai_client))
    graph.add_node("generate", lambda s: generate(s, openai_client))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(state: AgentState, db: Session, qdrant_client, openai_client) -> AgentState:
    compiled = build_graph(db, qdrant_client, openai_client)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
