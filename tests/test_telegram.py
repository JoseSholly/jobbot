import httpx
import pytest
import respx

from jobbot.adapters.telegram import TelegramClient, TelegramError, TelegramNotifier
from jobbot.interfaces.notifier import Button, OutgoingMessage, RecipientUnavailable

URL = "https://api.telegram.org/botTOKEN/sendMessage"


@respx.mock
async def test_send_message_payload():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json={"ok": True, "result": {}}))
    async with httpx.AsyncClient() as client:
        notifier = TelegramNotifier(TelegramClient("TOKEN", client))
        await notifier.send(42, OutgoingMessage("<b>hi</b>", [[Button("💾 1", "s:abc")]]))
    body = route.calls[0].request.read().decode()
    assert '"parse_mode":"HTML"' in body
    assert '"is_disabled":true' in body
    assert '"callback_data":"s:abc"' in body


@respx.mock
async def test_blocked_user_raises_recipient_unavailable():
    respx.post(URL).mock(
        return_value=httpx.Response(
            403,
            json={"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"},
        )
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(RecipientUnavailable):
            await TelegramNotifier(TelegramClient("TOKEN", client)).send(1, OutgoingMessage("x"))


@respx.mock
async def test_flood_wait_then_success_and_bad_request():
    respx.post(URL).mock(
        side_effect=[
            httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many",
                    "parameters": {"retry_after": 0},
                },
            ),
            httpx.Response(200, json={"ok": True, "result": {}}),
            httpx.Response(400, json={"ok": False, "error_code": 400, "description": "bad html"}),
        ]
    )
    async with httpx.AsyncClient() as client:
        tg = TelegramClient("TOKEN", client)
        await tg.call("sendMessage", {})
        with pytest.raises(TelegramError):
            await tg.call("sendMessage", {})
