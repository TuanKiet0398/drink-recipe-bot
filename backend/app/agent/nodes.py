from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.state import AgentState
from app.db.models import Favourite, Message


def fetch_history(state: AgentState, db: Session, limit: int = 10) -> AgentState:
    rows = (
        db.execute(
            select(Message)
            .where(Message.user_id == state.user_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    state.history = [{"role": m.role, "content": m.content} for m in rows]

    favourite_rows = (
        db.execute(select(Favourite).where(Favourite.user_id == state.user_id))
        .scalars()
        .all()
    )
    state.favourites = [f.drink_name for f in favourite_rows]
    return state


def retrieve(
    state: AgentState,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
    top_k: int = 5,
) -> AgentState:
    embedding = (
        openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=state.incoming_text,
        )
        .data[0]
        .embedding
    )
    hits = qdrant_client.search(collection_name=collection, query_vector=embedding, limit=top_k)
    state.retrieved_chunks = [hit.payload.get("text", "") for hit in hits]
    return state
