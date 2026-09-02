import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_message(chat_id: str, text: str) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        logger.error("Telegram sendMessage failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
