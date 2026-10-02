"""MyJobMag (Nigeria) search-results scraper. Disabled by default; see docs/sources.md.

Isolated and forgiving: if the markup changes we fall back to "any link to /job/...".
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.adapters.sources.scraping import first, job_links, split_title_company, text_of
from jobbot.domain.models import RawJob, Region
from jobbot.interfaces.sources import SearchContext

BASE = "https://www.myjobmag.com"
SEARCH = BASE + "/search/jobs"
JOB_HREF = re.compile(r"^(https://www\.myjobmag\.com)?/job/[^/?#]+$")


def parse(html: str) -> list[RawJob]:
    tree = HTMLParser(html)
    jobs: list[RawJob] = []
    for card in tree.css("li.job-list-li, li.job-info, div.job-info"):
        link = first(card, "h2 a", "a[href*='/job/']")
        if link is None:
            continue
        title, company = split_title_company(text_of(link))
        href = link.attributes.get("href") or ""
        jobs.append(
            RawJob(
                source="myjobmag",
                url=href if href.startswith("http") else BASE + href,
                title=title,
                company=company,
                description=text_of(first(card, "li.job-desc", ".job-desc", "p")),
                location=text_of(first(card, ".job-location", "li.location")) or "Nigeria",
                remote=None,
                posted_at=parse_date(text_of(first(card, "#job-date", ".job-date"))),
                region_hint=Region.NG,
            )
        )
    if jobs:
        return jobs
    # Fallback when the card markup has changed.
    for url, label in job_links(html, BASE, JOB_HREF):
        title, company = split_title_company(label)
        jobs.append(
            RawJob(
                source="myjobmag",
                url=url,
                title=title,
                company=company,
                location="Nigeria",
                region_hint=Region.NG,
            )
        )
    return jobs


class MyJobMagSource(BaseSource):
    name = "myjobmag"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        pages = int(self.options.get("pages_per_keyword", 1))
        for keyword in ctx.keywords:
            for page in range(1, pages + 1):
                params = {"q": keyword} | ({"currentpage": page} if page > 1 else {})
                batch = parse(await self.get_text(SEARCH, params=params))
                jobs.extend(batch)
                if not batch:
                    break
        return jobs
