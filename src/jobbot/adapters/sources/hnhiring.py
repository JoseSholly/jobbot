"""Hacker News "Ask HN: Who is hiring?" (monthly) via the free Algolia HN API.

Each top-level comment is one job post, usually starting with a line like
"Acme | Senior Python Engineer | Remote (EU, Africa) | Full-time | https://acme.com/jobs".
Hundreds of posts a month, heavy on Python/Django/AI roles. Only remote-friendly posts are kept.
"""

from __future__ import annotations

import re

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.domain.skills import TITLE_WORDS
from jobbot.domain.text import contains_term, strip_html
from jobbot.interfaces.sources import SearchContext

SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
ITEM = "https://hn.algolia.com/api/v1/items/{id}"
POST_URL = "https://news.ycombinator.com/item?id={id}"
_FIRST_LINE_RE = re.compile(r"<p>|\n")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _first_line(html: str) -> str:
    return strip_html(_FIRST_LINE_RE.split(html or "", maxsplit=1)[0])


def parse_post(comment: dict) -> RawJob | None:
    text = comment.get("text") or ""
    header = _first_line(text)
    parts = [p.strip() for p in header.split("|") if p.strip()]
    if len(parts) < 2:
        return None
    company = parts[0]
    rest = parts[1:]
    title = next(
        (p for p in rest if any(contains_term(p.lower(), w) for w in TITLE_WORDS) and not _URL_RE.match(p)),
        None,
    )
    location = next((p for p in rest if contains_term(p.lower(), "remote")), "")
    if not title or not location:
        return None  # keep remote engineering posts we can label confidently
    return RawJob(
        source="hn-hiring",
        url=POST_URL.format(id=comment.get("id")),
        title=title[:120],
        company=company[:80],
        description=text,
        location=location,
        remote=True,
        posted_at=parse_date(comment.get("created_at_i") or comment.get("created_at")),
    )


def parse_thread(item: dict) -> list[RawJob]:
    jobs = []
    for child in item.get("children") or []:
        if child.get("type", "comment") != "comment":
            continue
        job = parse_post(child)
        if job is not None:
            jobs.append(job)
    return jobs


class HNHiringSource(BaseSource):
    name = "hnhiring"

    async def latest_thread_id(self) -> int | None:
        data = await self.get_json(SEARCH, params={"tags": "story,author_whoishiring", "hitsPerPage": 10})
        for hit in data.get("hits", []):
            if (hit.get("title") or "").lower().startswith("ask hn: who is hiring"):
                return int(hit["objectID"])
        return None

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        thread_id = await self.latest_thread_id()
        if thread_id is None:
            return []
        return parse_thread(await self.get_json(ITEM.format(id=thread_id)))
