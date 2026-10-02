"""RemoteOK public API: https://remoteok.com/api.

Their terms ask for a link back to RemoteOK; every job URL we send points to remoteok.com.
"""

from __future__ import annotations

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

URL = "https://remoteok.com/api"


def parse(payload: list) -> list[RawJob]:
    jobs = []
    for item in payload:
        if not isinstance(item, dict) or "position" not in item:
            continue  # first element is a legal notice
        jobs.append(
            RawJob(
                source="remoteok",
                url=item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
                title=item.get("position", ""),
                company=item.get("company", ""),
                description=item.get("description", ""),
                location=item.get("location", "") or "Worldwide",
                remote=True,
                posted_at=parse_date(item.get("date") or item.get("epoch")),
            )
        )
    return jobs


class RemoteOKSource(BaseSource):
    name = "remoteok"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        return parse(await self.get_json(URL))
