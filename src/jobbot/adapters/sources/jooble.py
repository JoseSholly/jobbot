"""Jooble REST API (free key from https://jooble.org/api/about). Our main Nigeria source."""

from __future__ import annotations

import logging

from jobbot.adapters.http import request
from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob, Region
from jobbot.domain.regions import is_nigerian
from jobbot.interfaces.sources import SearchContext

log = logging.getLogger(__name__)

URL = "https://jooble.org/api/{key}"


def parse(payload: dict) -> list[RawJob]:
    jobs = []
    for item in payload.get("jobs", []):
        location = item.get("location", "") or ""
        jobs.append(
            RawJob(
                source="jooble",
                url=item.get("link", ""),
                title=item.get("title", ""),
                company=item.get("company", ""),
                description=item.get("snippet", ""),
                location=location or "Nigeria",
                remote=None,
                posted_at=parse_date(item.get("updated")),
                region_hint=Region.NG if (not location or is_nigerian(location)) else None,
            )
        )
    return jobs


class JoobleSource(BaseSource):
    name = "jooble"

    def __init__(self, *args, api_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        if not self.api_key:
            log.info("jooble: no JOOBLE_API_KEY; skipping")
            return []
        pages = int(self.options.get("pages_per_keyword", 1))
        jobs: list[RawJob] = []
        for keyword in ctx.keywords or ["developer"]:
            for page in range(1, pages + 1):
                resp = await request(
                    self.client,
                    "POST",
                    URL.format(key=self.api_key),
                    json={"keywords": keyword, "location": ctx.nigeria_location, "page": str(page)},
                )
                batch = parse(resp.json())
                jobs.extend(batch)
                if not batch:
                    break
        return jobs
