import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.clients import ensure_collection
from app.agent.state import AgentState
from app.db.models import Favourite, Message
from app.retry import retry_once
from app.token_usage import log_token_usage


def fetch_history(state: AgentState, db: Session, limit: int = 10) -> AgentState:
    rows = (
        db.execute(
            select(Message)
            .where(Message.user_id == state.user_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    rows = list(reversed(rows))
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
    db: Session,
    qdrant_client,
    openai_client,
    collection: str = "matcha_knowledge",
    top_k: int = 5,
    score_threshold: float = 0.35,
) -> AgentState:
    embedding_model = "text-embedding-3-small"
    response = retry_once(
        lambda: openai_client.embeddings.create(
            model=embedding_model,
            input=state.incoming_text,
        )
    )
    log_token_usage(db, state.user_id, "embedding", embedding_model, response.usage)
    embedding = response.data[0].embedding

    ensure_collection(qdrant_client, collection=collection)

    try:
        hits = retry_once(
            lambda: qdrant_client.search(
                collection_name=collection,
                query_vector=embedding,
                limit=top_k,
                score_threshold=score_threshold,
            )
        )
    except Exception:
        # Tolerate a not-yet-existing (or otherwise unreachable) collection:
        # fall back to no retrieved context rather than failing the whole
        # agent turn.
        state.retrieved_chunks = []
        return state

    state.retrieved_chunks = [hit.payload.get("text", "") for hit in hits]
    return state


def _build_system_prompt(state: AgentState) -> str:
    favourites = ", ".join(state.favourites) or "none known yet"
    context = "\n".join(f"- {chunk}" for chunk in state.retrieved_chunks) or "(no matching knowledge found)"
    return (
        "You are a premium matcha and tea ceremony consultant for this specific shop. "
        f"The user's known favourite drinks: {favourites}. "
        f"Relevant knowledge (this is everything the shop actually offers — only recommend from this):\n{context}\n"
        "Only recommend or describe drinks/recipes that appear in the knowledge above. "
        "If the user asks about something not covered there, say the shop doesn't currently "
        "have that, and suggest one of the drinks from the knowledge above instead. "
        "Never invent a drink, ingredient, or brewing method that isn't in the knowledge — "
        "not even from your own general knowledge of drinks outside this shop. "
        "If the knowledge above says '(no matching knowledge found)', you MUST tell the user "
        "the shop doesn't have a recipe for that and offer to suggest something from what the "
        "shop does have — do not describe how to make the drink they asked about under any "
        "circumstances in that case."
    )


def generate(state: AgentState, db: Session, openai_client, model: str = "gpt-4o-mini") -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    messages.extend(state.history)
    messages.append({"role": "user", "content": state.incoming_text})

    response = retry_once(lambda: openai_client.chat.completions.create(model=model, messages=messages))
    log_token_usage(db, state.user_id, "generate", model, response.usage)
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
    log_token_usage(db, state.user_id, "extract_favourite", model, response.usage)
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
