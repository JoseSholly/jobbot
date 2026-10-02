"""Outbound messaging contract (Telegram in production, a list in tests)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class Button:
    text: str
    callback_data: str


@dataclass(slots=True)
class OutgoingMessage:
    text: str  # Telegram-flavoured HTML
    buttons: list[list[Button]] | None = None


class RecipientUnavailable(Exception):
    """The chat can no longer receive messages (bot blocked, chat deleted)."""


class Notifier(Protocol):
    async def send(self, chat_id: int, message: OutgoingMessage) -> None: ...


class FileDownloader(Protocol):
    async def download(self, file_id: str) -> bytes: ...
