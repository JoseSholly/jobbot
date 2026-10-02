"""We Work Remotely category RSS feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

log = logging.getLogger(__name__)


def parse(xml_text: str) -> list[RawJob]:
    root = ET.fromstring(xml_text)
    jobs = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        # Titles look like "Company: Job Title".
        company, sep, title = raw_title.partition(":")
        if not sep:
            company, title = "", raw_title
        jobs.append(
            RawJob(
                source="weworkremotely",
                url=(item.findtext("link") or item.findtext("guid") or "").strip(),
                title=title.strip(),
                company=company.strip(),
                description=item.findtext("description") or "",
                location=(item.findtext("region") or "Anywhere in the World").strip(),
                remote=True,
                posted_at=parse_date(item.findtext("pubDate")),
            )
        )
    return jobs


class WeWorkRemotelySource(BaseSource):
    name = "weworkremotely"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        for feed in self.options.get("feeds", []):
            try:
                jobs.extend(parse(await self.get_text(feed)))
            except Exception as exc:  # one bad feed shouldn't drop the others
                log.warning("WWR feed %s failed: %s", feed, exc)
        return jobs
