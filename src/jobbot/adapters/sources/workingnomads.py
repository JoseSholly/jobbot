"""Working Nomads public JSON feed: https://www.workingnomads.com/api/exposed_jobs/."""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://www.workingnomads.com/api/exposed_jobs/"


def _get(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return value if isinstance(value, str) else ", ".join(map(str, value))
    return ""


def parse(payload: list) -> list[RawJob]:
    jobs = []
    for item in payload if isinstance(payload, list) else payload.get("jobs", []):
        if not isinstance(item, dict):
            continue
        tags = _get(item, "tags")
        description = _get(item, "description", "descriptionHtml")
        jobs.append(
            RawJob(
                source="workingnomads",
                url=_get(item, "url"),
                title=_get(item, "title"),
                company=_get(item, "company_name", "companyName"),
                description=f"{description} {tags}".strip(),
                location=_get(item, "location") or "Anywhere",
                remote=True,
                posted_at=parse_date(item.get("pub_date") or item.get("publishedAt")),
            )
        )
    return jobs


class WorkingNomadsSource(BaseSource):
    name = "workingnomads"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        return parse(await self.get_json(URL))
