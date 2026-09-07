import json
import logging
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.clients import get_or_create_collection
from app.agent.state import AgentState
from app.db.models import Favourite, Message
from app.metrics import RETRIEVE_CHUNKS
from app.retry import retry_once
from app.token_usage import log_token_usage

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

# The bot's personality/tone — see SOUL.md for the full description. Read
# once and cached; editing it requires a server restart to take effect.
SOUL_PATH = Path(__file__).resolve().parent.parent.parent / "SOUL.md"


@lru_cache
def _load_soul() -> str:
    try:
        return SOUL_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


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

    favourite_rows = db.execute(select(Favourite).where(Favourite.user_id == state.user_id)).scalars().all()
    state.favourites = [f.drink_name for f in favourite_rows]
    return state


def rewrite_query(
    question: str, history: list[dict], chat_client, model: str, db: Session, user_id: int | None
) -> str:
    """Condenses the conversation + question into a focused knowledge-base
    search query. Falls back to the original question if the LLM call
    fails, so retrieval degrades to a single (still-valid) search rather
    than failing the chat turn."""
    prompt = (
        "You are about to search a knowledge base to answer the user's question.\n"
        f"Conversation so far: {history}\n"
        f"User's current question: {question}\n\n"
        "Condense this into a single short, specific search query most likely "
        "to surface relevant content, folding in any needed context from the "
        "conversation. Respond ONLY with the query text, nothing else."
    )

    def _call():
        return chat_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        response = retry_once(_call, call_type="rewrite_query", model=model)
    except Exception:
        logger.exception("rewrite_query failed; falling back to the original question")
        return question

    log_token_usage(db, user_id, "rewrite_query", model, response.usage)
    rewritten = (response.choices[0].message.content or "").strip()
    return rewritten or question


def rerank(
    question: str, chunks: list[str], chat_client, model: str, db: Session, user_id: int | None
) -> list[str]:
    """Reorders `chunks` by relevance to `question` via an LLM call. Falls
    back to the original (retrieval-score) order if the call fails or
    returns an incomplete ranking."""
    if len(chunks) <= 1:
        return chunks

    numbered = "\n\n".join(f"# CHUNK {i + 1}:\n{chunk}" for i, chunk in enumerate(chunks))
    prompt = (
        f"The user asked: {question}\n\n"
        "Rank the following chunks by relevance to the question, most "
        'relevant first. Respond with strict JSON: {"order": [chunk numbers, '
        "most relevant first]}, including every chunk number exactly once.\n\n"
        f"{numbered}"
    )

    def _call():
        return chat_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

    try:
        response = retry_once(_call, call_type="rerank", model=model)
        log_token_usage(db, user_id, "rerank", model, response.usage)
        order = json.loads(response.choices[0].message.content)["order"]
        reranked = [chunks[i - 1] for i in order if 1 <= i <= len(chunks)]
        if len(reranked) == len(chunks):
            return reranked
    except Exception:
        logger.exception("rerank failed; keeping retrieval order")
    return chunks


def retrieve(
    state: AgentState,
    db: Session,
    chroma_client,
    chat_client,
    embedding_client,
    chat_model: str,
    collection: str = "matcha_knowledge",
    retrieval_k: int = 10,
    final_k: int = 5,
    score_threshold: float = 0.50,
) -> AgentState:
    def _embed(text: str) -> list[float]:
        response = retry_once(
            lambda: embedding_client.embeddings.create(model=EMBEDDING_MODEL, input=text),
            call_type="embedding",
            model=EMBEDDING_MODEL,
        )
        log_token_usage(db, state.user_id, "embedding", EMBEDDING_MODEL, response.usage)
        return response.data[0].embedding

    try:
        coll = get_or_create_collection(chroma_client, collection)

        rewritten = rewrite_query(
            state.incoming_text, state.history, chat_client, chat_model, db, state.user_id
        )
        query_texts = [state.incoming_text]
        if rewritten != state.incoming_text:
            query_texts.append(rewritten)

        best_scores: dict[str, float] = {}
        for query_text in query_texts:
            embedding = _embed(query_text)
            result = coll.query(query_embeddings=[embedding], n_results=retrieval_k)
            texts = result["documents"][0] if result["documents"] else []
            distances = result["distances"][0] if result["distances"] else []
            for text, distance in zip(texts, distances, strict=False):
                score = 1 - distance
                if score >= score_threshold:
                    best_scores[text] = max(best_scores.get(text, score), score)
    except Exception:
        # Tolerate a not-yet-existing (or otherwise unreachable) collection:
        # fall back to no retrieved context rather than failing the whole
        # agent turn.
        logger.exception("retrieval failed for user_id=%s", state.user_id)
        state.retrieved_chunks = []
        RETRIEVE_CHUNKS.observe(0)
        return state

    merged = sorted(best_scores, key=best_scores.get, reverse=True)
    state.retrieved_chunks = rerank(state.incoming_text, merged, chat_client, chat_model, db, state.user_id)[
        :final_k
    ]
    RETRIEVE_CHUNKS.observe(len(state.retrieved_chunks))
    return state


def _build_system_prompt(state: AgentState) -> str:
    favourites = ", ".join(state.favourites) or "none known yet"
    context = "\n".join(f"- {chunk}" for chunk in state.retrieved_chunks) or "(no matching knowledge found)"
    soul = _load_soul()
    soul_section = f"{soul}\n\n" if soul else ""
    return (
        f"{soul_section}"
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


def generate(
    state: AgentState,
    db: Session,
    chat_client,
    model: str,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    messages.extend(state.history)
    messages.append({"role": "user", "content": state.incoming_text})

    def _stream_once() -> tuple[str, object]:
        parts: list[str] = []
        usage = None
        stream = chat_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
                if on_delta is not None:
                    try:
                        on_delta("".join(parts))
                    except Exception:
                        logger.exception("on_delta callback failed")
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
        return "".join(parts), usage

    reply_text, usage = retry_once(_stream_once, call_type="generate", model=model)
    log_token_usage(db, state.user_id, "generate", model, usage)
    state.reply = reply_text
    return state


def extract_favourite(state: AgentState, db: Session, chat_client, model: str) -> None:
    prompt = (
        "Extract whether the user expressed a favourite drink preference in this message. "
        'Respond with strict JSON: {"drink_name": "<name>"} or {"drink_name": null} if none. '
        f"Message: {state.incoming_text!r}"
    )
    response = chat_client.chat.completions.create(
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
