"""Arbeitnow public API: https://www.arbeitnow.com/api/job-board-api (EU-heavy, some remote)."""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://www.arbeitnow.com/api/job-board-api"


def parse(payload: dict) -> list[RawJob]:
    return [
        RawJob(
            source="arbeitnow",
            url=item.get("url", ""),
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            description=item.get("description", ""),
            location=item.get("location", ""),
            remote=bool(item.get("remote")),
            posted_at=parse_date(item.get("created_at")),
        )
        for item in payload.get("data", [])
    ]


class ArbeitnowSource(BaseSource):
    name = "arbeitnow"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        for page in range(1, int(self.options.get("max_pages", 3)) + 1):
            payload = await self.get_json(URL, params={"page": page})
            batch = parse(payload)
            jobs.extend(batch)
            if not (payload.get("links") or {}).get("next"):
                break
        return jobs
