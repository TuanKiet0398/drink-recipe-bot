import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.channel_manager import ChannelManager
from app.crypto import encrypt
from app.db.models import Channel


def _make_channel(db_session, key: str, bot_token: str, is_active: bool = True, channel_type: str = "telegram") -> Channel:
    channel = Channel(
        key=key,
        display_name=key,
        channel_type=channel_type,
        encrypted_credentials=encrypt(json.dumps({"bot_token": bot_token})),
        is_active=is_active,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


@pytest.mark.asyncio
async def test_sync_starts_a_task_for_a_new_active_channel(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)

        assert channel.id in manager._tasks
        mock_run_poller.assert_called_once_with(channel.id, "token-a")

        await manager.stop_all()


@pytest.mark.asyncio
async def test_sync_ignores_inactive_and_non_telegram_channels(db_session):
    _make_channel(db_session, "inactive", "token-x", is_active=False)
    _make_channel(db_session, "other-type", "token-y", channel_type="zalo")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        manager = ChannelManager()
        await manager.sync(db_session)

        assert manager._tasks == {}
        mock_run_poller.assert_not_called()


@pytest.mark.asyncio
async def test_sync_stops_task_for_deactivated_channel(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        task = manager._tasks[channel.id]

        channel.is_active = False
        db_session.commit()
        await manager.sync(db_session)

        assert channel.id not in manager._tasks
        assert task.cancelled() or task.cancelling()


@pytest.mark.asyncio
async def test_sync_restarts_task_when_token_changes(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        first_task = manager._tasks[channel.id]

        channel.encrypted_credentials = encrypt(json.dumps({"bot_token": "token-b"}))
        db_session.commit()
        await manager.sync(db_session)

        assert manager._tasks[channel.id] is not first_task
        mock_run_poller.assert_called_with(channel.id, "token-b")

        await manager.stop_all()


@pytest.mark.asyncio
async def test_sync_leaves_unchanged_channel_task_running(db_session):
    channel = _make_channel(db_session, "bot-a", "token-a")

    with patch("app.channel_manager.run_poller", new_callable=AsyncMock) as mock_run_poller:
        mock_run_poller.side_effect = lambda *a, **k: asyncio.Event().wait()
        manager = ChannelManager()
        await manager.sync(db_session)
        first_task = manager._tasks[channel.id]

        await manager.sync(db_session)

        assert manager._tasks[channel.id] is first_task
        assert mock_run_poller.call_count == 1

        await manager.stop_all()


async def test_sync_sets_the_active_channels_gauge(db_session):
    from prometheus_client import REGISTRY

    from app.channel_manager import ChannelManager

    manager = ChannelManager()
    await manager.sync(db_session)

    assert REGISTRY.get_sample_value("active_channels") == 0
