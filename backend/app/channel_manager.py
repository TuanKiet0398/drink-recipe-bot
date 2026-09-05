import asyncio
import json
import logging

from sqlalchemy.orm import Session

from app.crypto import decrypt
from app.db.models import Channel
from app.telegram_poller import run_poller

logger = logging.getLogger(__name__)


class ChannelManager:
    """Keeps one long-poll `asyncio.Task` running per active Telegram
    channel, reconciled against the database on every `sync()` call — at
    app startup, and after every admin_channels.py mutation, so channel
    changes take effect without a process restart.
    """

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._tokens: dict[int, str] = {}

    async def sync(self, db: Session) -> None:
        active_channels = (
            db.query(Channel).filter_by(is_active=True, channel_type="telegram").all()
        )
        active_ids = {c.id for c in active_channels}

        for channel_id in list(self._tasks):
            if channel_id not in active_ids:
                await self._stop(channel_id)

        for channel in active_channels:
            try:
                bot_token = json.loads(decrypt(channel.encrypted_credentials))["bot_token"]
            except Exception:
                logger.exception("Failed to decrypt credentials for channel_id=%s; skipping", channel.id)
                continue

            if channel.id in self._tasks and self._tokens.get(channel.id) == bot_token:
                continue
            if channel.id in self._tasks:
                await self._stop(channel.id)

            self._tokens[channel.id] = bot_token
            self._tasks[channel.id] = asyncio.create_task(run_poller(channel.id, bot_token))

    async def _stop(self, channel_id: int) -> None:
        task = self._tasks.pop(channel_id, None)
        self._tokens.pop(channel_id, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def stop_all(self) -> None:
        for channel_id in list(self._tasks):
            await self._stop(channel_id)


channel_manager = ChannelManager()
