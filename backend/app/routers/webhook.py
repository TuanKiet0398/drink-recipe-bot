import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agent.clients import get_chroma_client, get_openai_client
from app.agent.graph import run_agent
from app.agent.nodes import extract_favourite
from app.agent.state import AgentState
from app.config import get_settings
from app.db.base import get_db
from app.db.models import Message, User
from app.telegram_client import edit_message_text, send_chat_action, send_message

logger = logging.getLogger(__name__)
router = APIRouter()

FALLBACK_REPLY = "Sorry, having trouble right now — please try again in a bit."
THINKING_PLACEHOLDER = "🤔 Đang suy nghĩ..."

# Fire-and-forget background tasks (e.g. favourite extraction) are held here
# so the event loop doesn't garbage-collect them mid-flight — asyncio only
# holds a weak reference to tasks created via create_task.
_background_tasks: set[asyncio.Task] = set()

# Telegram's typing indicator expires after ~5s, so it's refreshed slightly
# more often than that for the whole duration of the agent run.
_TYPING_KEEPALIVE_INTERVAL = 4.0

# Minimum time between progressive edits of the streamed reply, to stay
# well under Telegram's per-chat rate limit for message edits.
_STREAM_EDIT_MIN_INTERVAL = 1.2


def _get_or_create_user(db: Session, telegram_user_id: str) -> User:
    user = db.query(User).filter_by(telegram_user_id=telegram_user_id).one_or_none()
    if user is None:
        user = User(telegram_user_id=telegram_user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class _StreamDeliverer:
    """Progressively delivers a streamed reply to Telegram as it's generated.

    `on_delta` is invoked from the worker thread running the agent graph
    (see `asyncio.to_thread` in `_handle_telegram_webhook`), so it schedules
    the actual Telegram call back onto the event loop rather than awaiting
    directly — `run_coroutine_threadsafe` is the standard bridge for that.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, chat_id: str) -> None:
        self._loop = loop
        self._chat_id = chat_id
        self.message_id: int | None = None
        self._last_sent = 0.0
        # Serializes Telegram calls so concurrently-scheduled deltas can't
        # all observe message_id as None and each send a brand-new message.
        self._lock = asyncio.Lock()

    def on_delta(self, text: str) -> None:
        asyncio.run_coroutine_threadsafe(self._maybe_deliver(text), self._loop)

    async def finalize(self, text: str) -> None:
        async with self._lock:
            await self._send(text)

    async def _maybe_deliver(self, text: str) -> None:
        async with self._lock:
            now = time.monotonic()
            if self.message_id is not None and (now - self._last_sent) < _STREAM_EDIT_MIN_INTERVAL:
                return
            await self._send(text)

    async def _send(self, text: str) -> None:
        if not text:
            return
        try:
            if self.message_id is None:
                self.message_id = await send_message(chat_id=self._chat_id, text=text)
            else:
                await edit_message_text(chat_id=self._chat_id, message_id=self.message_id, text=text)
            self._last_sent = time.monotonic()
        except Exception:
            logger.exception("stream delivery failed for chat_id=%s", self._chat_id)


async def _keepalive_typing(chat_id: str, user_id: int) -> None:
    while True:
        await asyncio.sleep(_TYPING_KEEPALIVE_INTERVAL)
        try:
            await send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            logger.exception("typing keepalive failed for user_id=%s", user_id)


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    # The webhook must always ACK with HTTP 200, regardless of internal
    # outcome — malformed payloads, agent failures, and Telegram delivery
    # errors are all logged and swallowed here rather than allowed to
    # propagate into a 5xx response.
    _verify_telegram_secret(request)
    try:
        return await _handle_telegram_webhook(request, db)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error processing Telegram webhook")
        return {}


def _verify_telegram_secret(request: Request) -> None:
    settings = get_settings()
    expected = settings.telegram_webhook_secret
    if not expected:
        # No secret configured (e.g. local dev) — skip the check.
        return
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret token")


async def _handle_telegram_webhook(request: Request, db: Session):
    payload = await request.json()
    message = payload.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")
    return await process_telegram_message(chat_id, telegram_user_id, text, db)


async def process_telegram_message(chat_id: str, telegram_user_id: str, text: str, db: Session):
    """Runs the agent for one incoming Telegram text message and delivers the reply.

    Shared by both the webhook route and the long-polling loop (`app.telegram_poller`)
    so the two ingestion paths can't drift in behavior.
    """
    if not chat_id or not telegram_user_id or not text:
        return {}

    user = _get_or_create_user(db, telegram_user_id)

    if user.blocked:
        return {}

    db.add(Message(user_id=user.id, role="user", content=text))
    db.commit()

    state = AgentState(user_id=user.id, chat_id=chat_id, incoming_text=text)

    try:
        await send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        logger.exception("send_chat_action failed for user_id=%s", user.id)

    loop = asyncio.get_running_loop()
    deliverer = _StreamDeliverer(loop, chat_id)
    try:
        # Post an immediate "thinking" placeholder so the user gets instant
        # feedback instead of staring at a blank chat until the first token
        # arrives — the streamed reply then edits this same message in place.
        deliverer.message_id = await send_message(chat_id=chat_id, text=THINKING_PLACEHOLDER)
    except Exception:
        logger.exception("thinking placeholder failed for user_id=%s", user.id)
    keepalive_task = asyncio.create_task(_keepalive_typing(chat_id, user.id))

    try:
        # Known non-blocking test-noise issue: get_chroma_client()/
        # get_openai_client() are evaluated here as argument expressions
        # even when run_agent is mocked out in a test, which can attempt
        # real client construction. Low risk to leave as-is; tests that
        # care stub these two getters directly (see test_webhook.py).
        #
        # run_agent makes blocking OpenAI/Chroma calls, so it runs off the
        # event loop thread — otherwise it would stall every other request
        # (including the admin API) for the duration of the LLM call.
        result = await asyncio.to_thread(
            run_agent,
            state,
            db=db,
            chroma_client=get_chroma_client(),
            openai_client=get_openai_client(),
            on_delta=deliverer.on_delta,
        )
        reply = result.reply or FALLBACK_REPLY
    except Exception:
        logger.exception("Agent run failed for user_id=%s", user.id)
        reply = FALLBACK_REPLY
    finally:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    db.add(Message(user_id=user.id, role="assistant", content=reply))
    db.commit()

    try:
        if deliverer.message_id is not None:
            await deliverer.finalize(reply)
        else:
            await send_message(chat_id=chat_id, text=reply)
    except Exception:
        logger.exception("send_message failed for user_id=%s", user.id)

    task = asyncio.create_task(_extract_favourite_background(state, user.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

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
