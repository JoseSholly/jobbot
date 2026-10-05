"""Python.org Job Board RSS: https://www.python.org/jobs/feed/rss/ (Python-only roles)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.domain.text import strip_html
from jobbot.interfaces.sources import SearchContext

URL = "https://www.python.org/jobs/feed/rss/"
_LOCATION_RE = re.compile(r"location\s*:?\s*(.{2,80}?)(?:\s{2,}|\.\s|$)", re.IGNORECASE)
_REMOTE_RE = re.compile(r"\b(remote|telecommut\w*|work from home|anywhere)\b", re.IGNORECASE)


def _title_company(raw_title: str) -> tuple[str, str]:
    # Feed titles look like "Senior Python Developer, Acme Inc" (title first, then company).
    title, sep, company = raw_title.partition(", ")
    return (title.strip(), company.strip()) if sep else (raw_title.strip(), "")


def parse(xml_text: str) -> list[RawJob]:
    root = ET.fromstring(xml_text)
    jobs = []
    for item in root.iter("item"):
        title, company = _title_company(item.findtext("title") or "")
        description = item.findtext("description") or ""
        plain = strip_html(description)
        match = _LOCATION_RE.search(plain)
        location = match.group(1).strip() if match else ""
        remote = bool(_REMOTE_RE.search(f"{title} {location} {plain[:600]}"))
        jobs.append(
            RawJob(
                source="python.org",
                url=(item.findtext("link") or item.findtext("guid") or "").strip(),
                title=title,
                company=company,
                description=description,
                location=location or ("Remote" if remote else ""),
                remote=remote,
                posted_at=parse_date(item.findtext("pubDate")),
            )
        )
    return jobs


class PythonJobsSource(BaseSource):
    name = "pythonjobs"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        return parse(await self.get_text(URL))
