"""Himalayas public API: https://himalayas.app/jobs/api (paginated, max 20 per page)."""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://himalayas.app/jobs/api"
PAGE_SIZE = 20


def parse(payload: dict) -> list[RawJob]:
    jobs = []
    for item in payload.get("jobs", []):
        restrictions = item.get("locationRestrictions") or []
        location = (
            ", ".join(r if isinstance(r, str) else r.get("name", "") for r in restrictions) or "Worldwide"
        )
        jobs.append(
            RawJob(
                source="himalayas",
                url=item.get("applicationLink") or item.get("guid") or "",
                title=item.get("title", ""),
                company=item.get("companyName", ""),
                description=item.get("description") or item.get("excerpt", ""),
                location=location,
                remote=True,
                posted_at=parse_date(item.get("pubDate")),
            )
        )
    return jobs


class HimalayasSource(BaseSource):
    name = "himalayas"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        max_pages = int(self.options.get("max_pages", 10))
        jobs: list[RawJob] = []
        for page in range(max_pages):
            payload = await self.get_json(URL, params={"limit": PAGE_SIZE, "offset": page * PAGE_SIZE})
            batch = parse(payload)
            jobs.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        return jobs
