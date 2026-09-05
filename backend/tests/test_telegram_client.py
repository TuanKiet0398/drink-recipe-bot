import httpx
import pytest

from app.telegram_client import get_me, send_chat_action, send_message


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


@pytest.mark.asyncio
async def test_get_me_returns_bot_info_for_a_valid_token():
    import respx

    with respx.mock:
        respx.post("https://api.telegram.org/botTEST_TOKEN/getMe").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"id": 1, "username": "my_shop_bot"}})
        )

        info = await get_me("TEST_TOKEN")

        assert info["username"] == "my_shop_bot"


@pytest.mark.asyncio
async def test_get_me_raises_a_clear_error_for_an_invalid_token():
    import respx

    with respx.mock:
        respx.post("https://api.telegram.org/botBAD_TOKEN/getMe").mock(
            return_value=httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        )

        with pytest.raises(ValueError, match="Unauthorized"):
            await get_me("BAD_TOKEN")
