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
