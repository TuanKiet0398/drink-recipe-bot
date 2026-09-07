import asyncio
import logging

from app.db.base import SessionLocal
from app.metrics import record_poll_error, record_telegram_message
from app.routers.webhook import process_telegram_message
from app.telegram_client import delete_webhook, get_updates

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 30
_ERROR_BACKOFF = 5.0


async def run_poller(channel_id: int, bot_token: str) -> None:
    """Long-polls Telegram for new messages on behalf of one channel."""
    try:
        await delete_webhook(bot_token)
    except Exception:
        logger.exception("Failed to delete existing Telegram webhook for channel_id=%s", channel_id)

    offset: int | None = None
    logger.info("Telegram long-polling started for channel_id=%s", channel_id)
    while True:
        try:
            updates = await get_updates(bot_token, offset=offset, timeout=_POLL_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram getUpdates failed for channel_id=%s; retrying shortly", channel_id)
            record_poll_error(channel_id)
            await asyncio.sleep(_ERROR_BACKOFF)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                await _handle_update(channel_id, bot_token, update)
            except Exception:
                logger.exception(
                    "Failed to process Telegram update %s for channel_id=%s", update.get("update_id"), channel_id
                )


async def _handle_update(channel_id: int, bot_token: str, update: dict) -> None:
    message = update.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    if chat_id and telegram_user_id and text:
        record_telegram_message(channel_id, "in")

    db = SessionLocal()
    try:
        await process_telegram_message(channel_id, bot_token, chat_id, telegram_user_id, text, db)
    finally:
        db.close()
