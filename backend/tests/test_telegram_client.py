import httpx
import pytest

from app.telegram_client import send_message


@pytest.mark.asyncio
async def test_send_message_posts_to_telegram_api(monkeypatch, respx_mock=None):
    import respx

    with respx.mock:
        route = respx.post(
            "https://api.telegram.org/botTEST_TOKEN/sendMessage"
        ).mock(return_value=httpx.Response(200, json={"ok": True}))

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST_TOKEN")
        from app import config

        config.get_settings.cache_clear()

        await send_message(chat_id="42", text="hello")

        assert route.called
        sent = route.calls.last.request
        assert b'"chat_id": "42"' in sent.content or b'"chat_id":"42"' in sent.content

        config.get_settings.cache_clear()
