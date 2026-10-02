"""Shared HTTP client factory + retry policy for all outbound calls."""

from __future__ import annotations

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def make_client(timeout: float = 30.0, user_agent: str = "JobBot/0.1") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": user_agent, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"},
        follow_redirects=True,
    )


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (408, 425, 429, 500, 502, 503, 504)
    return isinstance(exc, httpx.TransportError)


def retrying(attempts: int = 3) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_retryable),
        reraise=True,
    )


async def request(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """Send a request with retries on transient failures; raise on HTTP errors."""
    async for attempt in retrying():
        with attempt:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
    raise AssertionError("unreachable")  # pragma: no cover
