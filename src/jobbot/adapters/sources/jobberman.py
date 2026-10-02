"""Jobberman (Nigeria) search-results scraper. Disabled by default; see docs/sources.md."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from jobbot.adapters.sources.base import BaseSource
from jobbot.adapters.sources.scraping import first, job_links, text_of
from jobbot.domain.models import RawJob, Region
from jobbot.interfaces.sources import SearchContext

BASE = "https://www.jobberman.com"
SEARCH = BASE + "/jobs"
JOB_HREF = re.compile(r"^(https://www\.jobberman\.com)?/listings/[^/?#]+")


def parse(html: str) -> list[RawJob]:
    tree = HTMLParser(html)
    jobs: list[RawJob] = []
    for card in tree.css("div[data-cy='listing-cards-components']"):
        link = first(card, "a[data-cy='listing-title-link']", "a[href*='/listings/']")
        if link is None:
            continue
        href = link.attributes.get("href") or ""
        company = text_of(first(card, "p.text-sm.text-link-500", "a[href*='/company/']"))
        meta = [text_of(n) for n in card.css("span.rounded")]
        jobs.append(
            RawJob(
                source="jobberman",
                url=href if href.startswith("http") else BASE + href,
                title=text_of(link),
                company=company,
                description=text_of(first(card, "p.text-sm.text-gray-500", "div.text-sm p")),
                location=(meta[0] if meta else "") or "Nigeria",
                remote=None,
                region_hint=Region.NG,
            )
        )
    if jobs:
        return jobs
    for url, label in job_links(html, BASE, JOB_HREF):
        jobs.append(
            RawJob(source="jobberman", url=url, title=label, location="Nigeria", region_hint=Region.NG)
        )
    return jobs


class JobbermanSource(BaseSource):
    name = "jobberman"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        pages = int(self.options.get("pages_per_keyword", 1))
        for keyword in ctx.keywords:
            for page in range(1, pages + 1):
                params = {"q": keyword} | ({"page": page} if page > 1 else {})
                batch = parse(await self.get_text(SEARCH, params=params))
                jobs.extend(batch)
                if not batch:
                    break
        return jobs
