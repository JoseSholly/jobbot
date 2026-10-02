"""Shared helpers for sources: HTTP access and date parsing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from jobbot.adapters.http import request


class BaseSource:
    """Gives subclasses a shared client, retries and a politeness delay."""

    name = "base"

    def __init__(
        self, client: httpx.AsyncClient, options: dict[str, Any] | None = None, delay_seconds: float = 0.0
    ):
        self.client = client
        self.options = options or {}
        self.delay_seconds = delay_seconds

    async def get_json(self, url: str, **kwargs) -> Any:
        return (await request(self.client, "GET", url, **kwargs)).json()

    async def get_text(self, url: str, **kwargs) -> str:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return (await request(self.client, "GET", url, **kwargs)).text


def parse_date(value: Any) -> datetime | None:
    """Accept ISO strings, RFC 822 strings, epoch seconds or epoch milliseconds."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, int | float) or (isinstance(value, str) and value.isdigit()):
            ts = float(value)
            if ts > 1e12:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        text = str(value).strip()
        try:
            iso = text.replace("Z", "+00:00")
            # Trim >6 fractional digits (Jooble returns 7) which fromisoformat rejects on 3.11-.
            if "." in iso:
                head, _, tail = iso.partition(".")
                digits = "".join(ch for ch in tail if ch.isdigit())
                rest = tail[len(digits) :]
                iso = f"{head}.{digits[:6]}{rest}"
            dt = datetime.fromisoformat(iso.replace(" ", "T", 1) if "T" not in iso else iso)
        except ValueError:
            dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return None
