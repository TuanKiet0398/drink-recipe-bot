import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_message(chat_id: str, text: str) -> int | None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        logger.error("Telegram sendMessage failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
    return response.json().get("result", {}).get("message_id")


async def edit_message_text(chat_id: str, message_id: int, text: str) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/editMessageText"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url, json={"chat_id": chat_id, "message_id": message_id, "text": text}
        )
    if response.status_code >= 400:
        # Telegram returns 400 for a no-op edit (identical text) — this is
        # expected when our throttling coincides with the model not having
        # produced new content since the last edit, so it's swallowed here
        # rather than logged as an error.
        if "message is not modified" in response.text.lower():
            return
        logger.error("Telegram editMessageText failed: %s %s", response.status_code, response.text)
        response.raise_for_status()


async def send_chat_action(chat_id: str, action: str = "typing") -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendChatAction"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "action": action})
    if response.status_code >= 400:
        logger.error("Telegram sendChatAction failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
