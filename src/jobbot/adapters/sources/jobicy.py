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
        count = int(self.options.get("count", 100))
        jobs = parse(await self.get_json(URL, params={"count": count}))  # latest, all fields
        # Then one search per top skill (e.g. python, django), which reaches older postings.
        for skill in ctx.skills[: int(self.options.get("max_tags", 3))]:
            tag = skill.strip().lower()
            if 3 <= len(tag) <= 50:
                jobs.extend(parse(await self.get_json(URL, params={"count": 50, "tag": tag})))
        return jobs
