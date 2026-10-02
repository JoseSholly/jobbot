"""Tell the admin when something goes wrong."""

from __future__ import annotations

import logging

from jobbot.interfaces.notifier import Notifier, OutgoingMessage
from jobbot.services.formatting import esc

log = logging.getLogger(__name__)


class AlertService:
    def __init__(self, notifier: Notifier | None, admin_chat_id: int | None):
        self.notifier = notifier
        self.admin_chat_id = admin_chat_id

    async def alert(self, title: str, details: str = "") -> None:
        log.error("ALERT %s %s", title, details)
        if not self.notifier or not self.admin_chat_id:
            return
        text = f"⚠️ <b>JobBot: {esc(title)}</b>"
        if details:
            text += f"\n<pre>{esc(details[:3500])}</pre>"
        try:
            await self.notifier.send(self.admin_chat_id, OutgoingMessage(text=text))
        except Exception:  # never let alerting crash the caller
            log.exception("failed to send admin alert")
