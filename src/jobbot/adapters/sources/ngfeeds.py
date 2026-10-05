"""Nigerian job boards via the RSS/Atom feeds they publish (MyJobMag, HotNigerianJobs, ...).

Feeds are the boards' own syndication channel, so this is lighter and more stable than
scraping. Every job is tagged Region.NG. Each configured feed can be:

  - a direct feed URL (RSS 2.0 or Atom), or
  - a web page that lists feeds (e.g. https://www.myjobmag.com/feeds/); the first link whose
    text contains `link_text` (or a <link rel="alternate"> feed) is followed automatically.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.adapters.sources.scraping import split_title_company
from jobbot.domain.models import RawJob, Region
from jobbot.domain.regions import is_nigerian
from jobbot.domain.text import strip_html
from jobbot.interfaces.sources import SearchContext

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml")


def looks_like_feed(text: str) -> bool:
    head = text.lstrip()[:500].lower()
    return head.startswith("<?xml") or "<rss" in head or "<feed" in head


def discover_feed(html: str, base_url: str, link_text: str = "") -> str | None:
    tree = HTMLParser(html)
    if link_text:
        wanted = link_text.lower()
        for a in tree.css("a[href]"):
            if wanted in a.text(strip=True).lower():
                return urljoin(base_url, a.attributes.get("href") or "")
    for link in tree.css("link[rel='alternate']"):
        if (link.attributes.get("type") or "").lower() in FEED_TYPES:
            return urljoin(base_url, link.attributes.get("href") or "")
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").lower()
        if href.endswith((".xml", ".rss", "/rss", "/feed", "/feed/")):
            return urljoin(base_url, a.attributes.get("href") or "")
    return None


def _job(source: str, url: str, raw_title: str, description: str, published) -> RawJob | None:
    title, company = split_title_company(strip_html(raw_title))
    if not title or not url:
        return None
    plain = strip_html(description)
    location = "Nigeria"
    for city in ("Lagos", "Abuja", "Port Harcourt", "Ibadan", "Kano", "Enugu", "Remote"):
        if city.lower() in plain[:400].lower() or city.lower() in title.lower():
            location = f"{city}, Nigeria" if city != "Remote" else "Remote (Nigeria)"
            break
    return RawJob(
        source=source,
        url=url.strip(),
        title=title,
        company=company,
        description=description,
        location=location,
        remote=True if "remote" in f"{title} {plain[:400]}".lower() else None,
        posted_at=parse_date(published),
        region_hint=Region.NG if (is_nigerian(location) or location.startswith("Remote")) else None,
    )


def parse_feed(xml_text: str, source: str) -> list[RawJob]:
    root = ET.fromstring(xml_text.lstrip().encode())
    jobs: list[RawJob] = []
    for item in root.iter("item"):  # RSS 2.0
        job = _job(
            source,
            item.findtext("link") or item.findtext("guid") or "",
            item.findtext("title") or "",
            item.findtext("description") or "",
            item.findtext("pubDate"),
        )
        if job:
            jobs.append(job)
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        link = entry.find(f"{ATOM}link")
        job = _job(
            source,
            link.get("href", "") if link is not None else "",
            entry.findtext(f"{ATOM}title") or "",
            entry.findtext(f"{ATOM}content") or entry.findtext(f"{ATOM}summary") or "",
            entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated"),
        )
        if job:
            jobs.append(job)
    for job in jobs:  # every feed here is a Nigerian board
        job.region_hint = job.region_hint or Region.NG
    return jobs


class NigerianFeedsSource(BaseSource):
    name = "ngfeeds"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        for feed in self.options.get("feeds") or []:
            name = feed.get("name") or feed["url"]
            try:
                text = await self.get_text(feed["url"])
                if not looks_like_feed(text):
                    found = discover_feed(text, feed["url"], feed.get("link_text", ""))
                    if not found:
                        log.warning("ngfeeds %s: no feed link found on %s", name, feed["url"])
                        continue
                    log.info("ngfeeds %s: using discovered feed %s", name, found)
                    text = await self.get_text(found)
                batch = parse_feed(text, f"ng:{name}")
                log.info("ngfeeds %s: %d jobs", name, len(batch))
                jobs.extend(batch)
            except Exception as exc:  # one broken feed must not hide the others
                log.warning("ngfeeds %s failed: %s", name, exc)
        return jobs
