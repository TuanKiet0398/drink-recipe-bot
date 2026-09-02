import json

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


def _build_system_prompt(state: AgentState) -> str:
    favourites = ", ".join(state.favourites) or "none known yet"
    context = "\n".join(f"- {chunk}" for chunk in state.retrieved_chunks) or "(no matching knowledge found)"
    return (
        "You are a premium matcha and tea ceremony consultant. "
        f"The user's known favourite drinks: {favourites}. "
        f"Relevant knowledge:\n{context}\n"
        "Answer helpfully and recommend products/brewing methods when relevant."
    )


def generate(state: AgentState, openai_client, model: str = "gpt-4o-mini") -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    messages.extend(state.history)
    messages.append({"role": "user", "content": state.incoming_text})

    response = openai_client.chat.completions.create(model=model, messages=messages)
    state.reply = response.choices[0].message.content
    return state


def extract_favourite(state: AgentState, db: Session, openai_client, model: str = "gpt-4o-mini") -> None:
    prompt = (
        "Extract whether the user expressed a favourite drink preference in this message. "
        'Respond with strict JSON: {"drink_name": "<name>"} or {"drink_name": null} if none. '
        f"Message: {state.incoming_text!r}"
    )
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return

    drink_name = parsed.get("drink_name")
    if not drink_name:
        return

    db.add(
        Favourite(
            user_id=state.user_id,
            drink_name=drink_name,
            confidence="inferred",
            source="chat",
        )
    )
    db.commit()
