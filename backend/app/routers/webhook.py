import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agent.clients import get_openai_client, get_qdrant_client
from app.agent.graph import run_agent
from app.agent.nodes import extract_favourite
from app.agent.state import AgentState
from app.db.base import get_db
from app.db.models import Message, User
from app.telegram_client import send_message

logger = logging.getLogger(__name__)
router = APIRouter()

FALLBACK_REPLY = "Sorry, having trouble right now — please try again in a bit."


def _get_or_create_user(db: Session, telegram_user_id: str) -> User:
    user = db.query(User).filter_by(telegram_user_id=telegram_user_id).one_or_none()
    if user is None:
        user = User(telegram_user_id=telegram_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    # The webhook must always ACK with HTTP 200, regardless of internal
    # outcome — malformed payloads, agent failures, and Telegram delivery
    # errors are all logged and swallowed here rather than allowed to
    # propagate into a 5xx response.
    try:
        return await _handle_telegram_webhook(request, db)
    except Exception:
        logger.exception("Unhandled error processing Telegram webhook")
        return {}


async def _handle_telegram_webhook(request: Request, db: Session):
    payload = await request.json()
    message = payload.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    if not chat_id or not telegram_user_id or not text:
        return {}

    user = _get_or_create_user(db, telegram_user_id)

    if user.blocked:
        return {}

    db.add(Message(user_id=user.id, role="user", content=text))
    db.commit()

    state = AgentState(user_id=user.id, chat_id=chat_id, incoming_text=text)

    try:
        result = run_agent(
            state,
            db=db,
            qdrant_client=get_qdrant_client(),
            openai_client=get_openai_client(),
        )
        reply = result.reply or FALLBACK_REPLY
    except Exception:
        logger.exception("Agent run failed for user_id=%s", user.id)
        reply = FALLBACK_REPLY

    db.add(Message(user_id=user.id, role="assistant", content=reply))
    db.commit()

    try:
        await send_message(chat_id=chat_id, text=reply)
    except Exception:
        logger.exception("send_message failed for user_id=%s", user.id)

    asyncio.create_task(_extract_favourite_background(state, user.id))

    return {}


async def _extract_favourite_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_favourite makes a blocking OpenAI call; run it off the
        # event loop thread so it doesn't stall other concurrent requests.
        await asyncio.to_thread(extract_favourite, state, db=db, openai_client=get_openai_client())
    except Exception:
        logger.exception("extract_favourite failed for user_id=%s", user_id)
    finally:
        db.close()
