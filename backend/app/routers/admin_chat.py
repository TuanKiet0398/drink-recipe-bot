import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import llm_settings
from app.agent.clients import get_chat_client, get_chat_model, get_chroma_client, get_embedding_client
from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.auth import require_admin
from app.db.base import get_db
from app.db.models import Channel, ConversationSummary, Message, User
from app.routers.webhook import DAILY_LIMIT_REPLY, spawn_background_extractions
from app.token_usage import get_daily_token_total

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/chat")

WEB_CHANNEL_TYPE = "web"
HISTORY_LIMIT = 50


class ChatPayload(BaseModel):
    message: str = Field(max_length=4000)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


def get_web_user(db: Session, username: str) -> User:
    """The `User` a signed-in account chats as. Every account shares one
    "web" channel, and the username sits in telegram_user_id, so all the
    existing per-user memory tables work unchanged."""
    channel = db.query(Channel).filter_by(channel_type=WEB_CHANNEL_TYPE).one_or_none()
    if channel is None:
        channel = Channel(
            key="web",
            display_name="Web chat",
            channel_type=WEB_CHANNEL_TYPE,
            encrypted_credentials="",
            is_active=True,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

    user = db.query(User).filter_by(channel_id=channel.id, telegram_user_id=username).one_or_none()
    if user is None:
        user = User(channel_id=channel.id, telegram_user_id=username)
        db.add(user)
    user.last_active_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def _find_web_user(db: Session, username: str) -> User | None:
    return (
        db.query(User)
        .join(Channel)
        .filter(Channel.channel_type == WEB_CHANNEL_TYPE, User.telegram_user_id == username)
        .one_or_none()
    )


@router.post("")
async def chat(
    payload: ChatPayload,
    db: Session = Depends(get_db),
    username: str = Depends(require_admin),
):
    user = get_web_user(db, username)
    if user.blocked:
        raise HTTPException(status_code=403, detail="Your account is blocked")

    chat_model = get_chat_model(db)
    limit = llm_settings.resolve(db).daily_token_limit
    if limit is not None and get_daily_token_total(db, user.id) >= limit:
        db.add(Message(user_id=user.id, role="user", content=payload.message))
        db.add(Message(user_id=user.id, role="assistant", content=DAILY_LIMIT_REPLY))
        db.commit()
        return {"reply": DAILY_LIMIT_REPLY, "model": chat_model}

    state = AgentState(user_id=user.id, chat_id=f"web:{user.id}", incoming_text=payload.message)
    try:
        # The message is saved only after the run: fetch_history then sees just
        # the earlier conversation, and generate appends the question once.
        # run_agent makes blocking LLM calls, so it runs off the event loop.
        result = await asyncio.to_thread(
            run_agent,
            state,
            db=db,
            chroma_client=get_chroma_client(),
            chat_client=get_chat_client(db),
            embedding_client=get_embedding_client(),
            chat_model=chat_model,
        )
    except Exception as exc:
        logger.exception("web chat failed for user_id=%s", user.id)
        db.rollback()
        db.add(Message(user_id=user.id, role="user", content=payload.message))
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.add(Message(user_id=user.id, role="user", content=payload.message))
    db.add(Message(user_id=user.id, role="assistant", content=result.reply))
    db.commit()

    # run_agent returns a new state; the extractors read reply and chunks from it.
    state.reply = result.reply
    state.retrieved_chunks = result.retrieved_chunks
    spawn_background_extractions(state, user.id)

    return {"reply": result.reply, "model": chat_model}


@router.get("/history")
def chat_history(db: Session = Depends(get_db), username: str = Depends(require_admin)):
    user = _find_web_user(db, username)
    if user is None:
        return []
    rows = (
        db.execute(
            select(Message)
            .where(Message.user_id == user.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(HISTORY_LIMIT)
        )
        .scalars()
        .all()
    )
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in reversed(rows)
    ]


@router.delete("/history", status_code=204)
def reset_chat_history(db: Session = Depends(get_db), username: str = Depends(require_admin)):
    """Forgets the conversation, not the person: favourites, customer notes
    and recommendation history stay."""
    user = _find_web_user(db, username)
    if user is not None:
        # The summary points at a message (last_summarized_message_id), so it goes first.
        db.execute(delete(ConversationSummary).where(ConversationSummary.user_id == user.id))
        db.execute(delete(Message).where(Message.user_id == user.id))
        db.commit()
    return Response(status_code=204)
