"""Remotive public API: https://remotive.com/api/remote-jobs (please keep to a few calls/day)."""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://remotive.com/api/remote-jobs"


def parse(payload: dict) -> list[RawJob]:
    return [
        RawJob(
            source="remotive",
            url=item.get("url", ""),
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            description=item.get("description", ""),
            location=item.get("candidate_required_location", "") or "Worldwide",
            remote=True,
            posted_at=parse_date(item.get("publication_date")),
        )
        for item in payload.get("jobs", [])
    ]


class RemotiveSource(BaseSource):
    name = "remotive"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        # Remotive asks for at most a few calls a day, so query a small list of categories
        # rather than one request per keyword. Category slugs: remotive.com/api/remote-jobs/categories
        categories = self.options.get("categories") or [None]
        jobs: list[RawJob] = []
        for category in categories:
            params = {"category": category} if category else {}
            jobs.extend(parse(await self.get_json(URL, params=params)))
        return jobs
