import httpx
import pytest

from app.telegram_client import send_chat_action, send_message


@pytest.mark.asyncio
async def test_send_message_posts_to_telegram_api():
    import respx

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )

        await send_message("TEST_TOKEN", chat_id="42", text="hello")

        assert route.called
        sent = route.calls.last.request
        assert b'"chat_id": "42"' in sent.content or b'"chat_id":"42"' in sent.content


@pytest.mark.asyncio
async def test_send_chat_action_posts_typing_to_telegram_api():
    import respx

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendChatAction").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await send_chat_action("TEST_TOKEN", chat_id="42")

        assert route.called
        sent = route.calls.last.request
        assert b'"action": "typing"' in sent.content or b'"action":"typing"' in sent.content
