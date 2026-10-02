"""Telegram Bot API adapter (plain HTTPS): sending messages and downloading files."""

from __future__ import annotations

import asyncio
import logging

import httpx

from jobbot.interfaces.notifier import OutgoingMessage, RecipientUnavailable

log = logging.getLogger(__name__)

API = "https://api.telegram.org"


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, token: str, client: httpx.AsyncClient):
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        self.token = token
        self.client = client

    async def call(self, method: str, payload: dict) -> dict:
        for attempt in range(4):
            resp = await self.client.post(f"{API}/bot{self.token}/{method}", json=payload)
            data = resp.json() if resp.content else {}
            if data.get("ok"):
                return data.get("result", {})
            code = data.get("error_code", resp.status_code)
            desc = data.get("description", resp.text[:200])
            if code == 429:  # flood control: wait as instructed
                wait = (data.get("parameters") or {}).get("retry_after", 2**attempt)
                log.warning("telegram 429, sleeping %ss", wait)
                await asyncio.sleep(min(float(wait), 60))
                continue
            if code >= 500 and attempt < 3:
                await asyncio.sleep(2**attempt)
                continue
            if code == 403 or "chat not found" in desc.lower():
                raise RecipientUnavailable(desc)
            raise TelegramError(f"{method} failed ({code}): {desc}")
        raise TelegramError(f"{method} failed after retries")


class TelegramNotifier:
    """Implements interfaces.notifier.Notifier."""

    def __init__(self, telegram: TelegramClient):
        self.telegram = telegram

    async def send(self, chat_id: int, message: OutgoingMessage) -> None:
        payload: dict = {
            "chat_id": chat_id,
            "text": message.text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if message.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": b.text, "callback_data": b.callback_data} for b in row]
                    for row in message.buttons
                ]
            }
        await self.telegram.call("sendMessage", payload)


class TelegramFileDownloader:
    """Implements interfaces.notifier.FileDownloader (bots can fetch files up to 20 MB)."""

    def __init__(self, telegram: TelegramClient):
        self.telegram = telegram

    async def download(self, file_id: str) -> bytes:
        info = await self.telegram.call("getFile", {"file_id": file_id})
        path = info.get("file_path")
        if not path:
            raise TelegramError("getFile returned no file_path")
        resp = await self.telegram.client.get(f"{API}/file/bot{self.telegram.token}/{path}")
        resp.raise_for_status()
        return resp.content


class ConsoleNotifier:
    """Prints messages instead of sending them (dry runs)."""

    async def send(self, chat_id: int, message: OutgoingMessage) -> None:
        print(f"\n----- to {chat_id} -----\n{message.text}")
        if message.buttons:
            print("[buttons] " + " | ".join(" ".join(b.text for b in row) for row in message.buttons))
