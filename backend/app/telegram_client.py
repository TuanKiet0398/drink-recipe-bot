import logging

import httpx

logger = logging.getLogger(__name__)


async def send_message(bot_token: str, chat_id: str, text: str) -> int | None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        logger.error("Telegram sendMessage failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
    return response.json().get("result", {}).get("message_id")


async def edit_message_text(bot_token: str, chat_id: str, message_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
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


async def get_updates(bot_token: str, offset: int | None, timeout: int = 30) -> list[dict]:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params: dict = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset
    # Long-poll timeout plus a margin for the round trip itself.
    async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
        response = await client.post(url, json=params)
    if response.status_code >= 400:
        logger.error("Telegram getUpdates failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
    return response.json().get("result", [])


async def delete_webhook(bot_token: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url)
    if response.status_code >= 400:
        logger.error("Telegram deleteWebhook failed: %s %s", response.status_code, response.text)
        response.raise_for_status()


async def send_chat_action(bot_token: str, chat_id: str, action: str = "typing") -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "action": action})
    if response.status_code >= 400:
        logger.error("Telegram sendChatAction failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
