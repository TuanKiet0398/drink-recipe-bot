import asyncio
import logging
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app import llm_settings
from app.agent.clients import get_chat_client, get_chat_model, get_chroma_client, get_embedding_client
from app.agent.graph import run_agent
from app.agent.nodes import (
    extract_customer_notes,
    extract_favourite,
    extract_recommendation,
    maybe_summarize,
)
from app.agent.state import AgentState
from app.db.models import Message, User
from app.metrics import record_daily_limit_hit, record_extraction, record_summarize, record_telegram_message
from app.telegram_client import edit_message_text, send_chat_action, send_message
from app.token_usage import get_daily_token_total

logger = logging.getLogger(__name__)

FALLBACK_REPLY = "Sorry, having trouble right now — please try again in a bit."
THINKING_PLACEHOLDER = "🤔 Đang suy nghĩ..."
DAILY_LIMIT_REPLY = (
    "Bạn đã đạt giới hạn sử dụng hôm nay, quay lại vào ngày mai nhé! "
    "(You've reached today's usage limit — please come back tomorrow.)"
)

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


def _get_or_create_user(db: Session, channel_id: int, telegram_user_id: str) -> User:
    user = db.query(User).filter_by(channel_id=channel_id, telegram_user_id=telegram_user_id).one_or_none()
    if user is None:
        user = User(channel_id=channel_id, telegram_user_id=telegram_user_id)
        db.add(user)
    user.last_active_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


class _StreamDeliverer:
    """Progressively delivers a streamed reply to Telegram as it's generated.

    `on_delta` is invoked from the worker thread running the agent graph
    (see `asyncio.to_thread` in `process_telegram_message`), so it schedules
    the actual Telegram call back onto the event loop rather than awaiting
    directly — `run_coroutine_threadsafe` is the standard bridge for that.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, bot_token: str, chat_id: str) -> None:
        self._loop = loop
        self._bot_token = bot_token
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
                self.message_id = await send_message(self._bot_token, chat_id=self._chat_id, text=text)
            else:
                await edit_message_text(
                    self._bot_token, chat_id=self._chat_id, message_id=self.message_id, text=text
                )
            self._last_sent = time.monotonic()
        except Exception:
            logger.exception("stream delivery failed for chat_id=%s", self._chat_id)


async def _keepalive_typing(bot_token: str, chat_id: str, user_id: int) -> None:
    while True:
        await asyncio.sleep(_TYPING_KEEPALIVE_INTERVAL)
        try:
            await send_chat_action(bot_token, chat_id=chat_id, action="typing")
        except Exception:
            logger.exception("typing keepalive failed for user_id=%s", user_id)


async def process_telegram_message(
    channel_id: int, bot_token: str, chat_id: str, telegram_user_id: str, text: str, db: Session
):
    """Runs the agent for one incoming Telegram text message and delivers
    the reply. Called from the per-channel long-poll loop in
    `app.telegram_poller`."""
    if not chat_id or not telegram_user_id or not text:
        return {}

    user = _get_or_create_user(db, channel_id, telegram_user_id)

    if user.blocked:
        return {}

    db.add(Message(user_id=user.id, role="user", content=text))
    db.commit()

    resolved_settings = llm_settings.resolve(db)
    if (
        resolved_settings.daily_token_limit is not None
        and get_daily_token_total(db, user.id) >= resolved_settings.daily_token_limit
    ):
        db.add(Message(user_id=user.id, role="assistant", content=DAILY_LIMIT_REPLY))
        db.commit()
        try:
            await send_message(bot_token, chat_id=chat_id, text=DAILY_LIMIT_REPLY)
        except Exception:
            logger.exception("send_message failed for user_id=%s", user.id)
        record_telegram_message(channel_id, "out")
        record_daily_limit_hit(channel_id)
        return {}

    state = AgentState(user_id=user.id, chat_id=chat_id, incoming_text=text)

    try:
        await send_chat_action(bot_token, chat_id=chat_id, action="typing")
    except Exception:
        logger.exception("send_chat_action failed for user_id=%s", user.id)

    loop = asyncio.get_running_loop()
    deliverer = _StreamDeliverer(loop, bot_token, chat_id)
    try:
        # Post an immediate "thinking" placeholder so the user gets instant
        # feedback instead of staring at a blank chat until the first token
        # arrives — the streamed reply then edits this same message in place.
        deliverer.message_id = await send_message(bot_token, chat_id=chat_id, text=THINKING_PLACEHOLDER)
    except Exception:
        logger.exception("thinking placeholder failed for user_id=%s", user.id)
    keepalive_task = asyncio.create_task(_keepalive_typing(bot_token, chat_id, user.id))

    try:
        # run_agent makes blocking OpenAI/Chroma calls, so it runs off the
        # event loop thread — otherwise it would stall every other request
        # (including the admin API) for the duration of the LLM call.
        #
        # on_delta is intentionally not wired up here: the graph's
        # `check_facts` node runs the guardrails self-check-facts rail after
        # `generate`, and it needs the complete reply before it can decide
        # whether to substitute a refusal — a live per-token Telegram edit
        # would leak an ungrounded answer before that check ever runs.
        result = await asyncio.to_thread(
            run_agent,
            state,
            db=db,
            chroma_client=get_chroma_client(),
            chat_client=get_chat_client(db),
            embedding_client=get_embedding_client(),
            chat_model=get_chat_model(db),
        )
        reply = result.reply or FALLBACK_REPLY
        retrieved_chunks = result.retrieved_chunks
    except Exception:
        logger.exception("Agent run failed for user_id=%s", user.id)
        reply = FALLBACK_REPLY
        retrieved_chunks = []
    finally:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    # run_agent returns a new AgentState (graph.py), so the pre-run `state`
    # object still has reply=="" and no retrieved chunks — carry both over so
    # the background extractors (which take `state`, not `result`) can read
    # them. extract_recommendation needs the chunks to check that what it is
    # about to remember is actually backed by the knowledge base.
    state.reply = reply
    state.retrieved_chunks = retrieved_chunks

    db.add(Message(user_id=user.id, role="assistant", content=reply))
    db.commit()

    try:
        if deliverer.message_id is not None:
            await deliverer.finalize(reply)
        else:
            await send_message(bot_token, chat_id=chat_id, text=reply)
    except Exception:
        logger.exception("send_message failed for user_id=%s", user.id)

    record_telegram_message(channel_id, "out")

    spawn_background_extractions(state, user.id)

    return {}


def spawn_background_extractions(state: AgentState, user_id: int) -> None:
    """Starts the post-turn memory work (favourite, summary, customer notes,
    recommendation) as fire-and-forget tasks. Shared by Telegram and web chat;
    must be called from inside the running event loop."""
    for coroutine in (
        _extract_favourite_background(state, user_id),
        _maybe_summarize_background(user_id),
        _extract_customer_notes_background(state, user_id),
        _extract_recommendation_background(state, user_id),
    ):
        task = asyncio.create_task(coroutine)
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


async def _extract_favourite_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_favourite makes a blocking OpenAI call; run it off the
        # event loop thread so it doesn't stall other concurrent requests.
        await asyncio.to_thread(
            extract_favourite,
            state,
            db=db,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("extract_favourite failed for user_id=%s", user_id)
        record_extraction("favourite", "error")
    finally:
        db.close()


async def _maybe_summarize_background(user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # summarize_conversation makes a blocking OpenAI call; run it off the
        # event loop thread so it doesn't stall other concurrent requests.
        await asyncio.to_thread(
            maybe_summarize,
            db,
            user_id,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("maybe_summarize failed for user_id=%s", user_id)
        record_summarize("error")
    finally:
        db.close()


async def _extract_customer_notes_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_customer_notes makes a blocking OpenAI call; run it off
        # the event loop thread so it doesn't stall other concurrent
        # requests.
        await asyncio.to_thread(
            extract_customer_notes,
            state,
            db=db,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("extract_customer_notes failed for user_id=%s", user_id)
        record_extraction("customer_notes", "error")
    finally:
        db.close()


async def _extract_recommendation_background(state: AgentState, user_id: int) -> None:
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        # extract_recommendation makes a blocking OpenAI call; run it off
        # the event loop thread so it doesn't stall other concurrent
        # requests.
        await asyncio.to_thread(
            extract_recommendation,
            state,
            db=db,
            chat_client=get_chat_client(db),
            model=get_chat_model(db),
        )
    except Exception:
        logger.exception("extract_recommendation failed for user_id=%s", user_id)
        record_extraction("recommendation", "error")
    finally:
        db.close()
