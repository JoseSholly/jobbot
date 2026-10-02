"""Jobicy public API: https://jobicy.com/api/v2/remote-jobs."""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://jobicy.com/api/v2/remote-jobs"


def parse(payload: dict) -> list[RawJob]:
    jobs = []
    for item in payload.get("jobs", []):
        geo = item.get("jobGeo") or "Anywhere"
        jobs.append(
            RawJob(
                source="jobicy",
                url=item.get("url", ""),
                title=item.get("jobTitle", ""),
                company=item.get("companyName", ""),
                description=item.get("jobDescription") or item.get("jobExcerpt", ""),
                location=geo,
                remote=True,
                posted_at=parse_date(item.get("pubDate")),
            )
        )
    return jobs


class JobicySource(BaseSource):
    name = "jobicy"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        payload = await self.get_json(URL, params={"count": int(self.options.get("count", 100))})
        return parse(payload)
