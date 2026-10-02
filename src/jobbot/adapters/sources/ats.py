"""Public ATS job boards of hand-picked companies: Greenhouse, Lever, Ashby."""

from __future__ import annotations

import logging

from jobbot.adapters.sources.base import BaseSource, parse_date
from jobbot.domain.models import RawJob
from jobbot.interfaces.sources import SearchContext

log = logging.getLogger(__name__)

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER = "https://api.lever.co/v0/postings/{token}"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def _remote_from(location: str) -> bool | None:
    return True if "remote" in location.lower() else None


def parse_greenhouse(payload: dict, token: str) -> list[RawJob]:
    jobs = []
    for item in payload.get("jobs", []):
        location = (item.get("location") or {}).get("name", "")
        jobs.append(
            RawJob(
                source=f"greenhouse:{token}",
                url=item.get("absolute_url", ""),
                title=item.get("title", ""),
                company=item.get("company_name") or token.title(),
                description=item.get("content", ""),
                location=location,
                remote=_remote_from(location),
                posted_at=parse_date(item.get("first_published") or item.get("updated_at")),
            )
        )
    return jobs


def parse_lever(payload: list, token: str) -> list[RawJob]:
    jobs = []
    for item in payload:
        categories = item.get("categories") or {}
        location = categories.get("location") or ", ".join(categories.get("allLocations") or [])
        workplace = (item.get("workplaceType") or "").lower()
        jobs.append(
            RawJob(
                source=f"lever:{token}",
                url=item.get("hostedUrl", ""),
                title=item.get("text", ""),
                company=token.title(),
                description=item.get("descriptionPlain") or item.get("description", ""),
                location=location,
                remote=True if workplace == "remote" else _remote_from(location),
                posted_at=parse_date(item.get("createdAt")),
            )
        )
    return jobs


def parse_ashby(payload: dict, token: str) -> list[RawJob]:
    jobs = []
    for item in payload.get("jobs", []):
        if item.get("isListed") is False:
            continue
        location = item.get("location", "") or ""
        jobs.append(
            RawJob(
                source=f"ashby:{token}",
                url=item.get("jobUrl", ""),
                title=item.get("title", ""),
                company=token.title(),
                description=item.get("descriptionPlain") or item.get("descriptionHtml", ""),
                location=location,
                remote=bool(item.get("isRemote")) or _remote_from(location),
                posted_at=parse_date(item.get("publishedAt")),
            )
        )
    return jobs


class ATSSource(BaseSource):
    name = "ats"

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        jobs: list[RawJob] = []
        boards = [
            ("greenhouse", GREENHOUSE, {"content": "true"}, parse_greenhouse),
            ("lever", LEVER, {"mode": "json"}, parse_lever),
            ("ashby", ASHBY, {}, parse_ashby),
        ]
        for kind, url, params, parser in boards:
            for token in self.options.get(kind) or []:
                try:
                    payload = await self.get_json(url.format(token=token), params=params)
                    jobs.extend(parser(payload, token))
                except Exception as exc:  # unknown token / board moved: skip that company
                    log.warning("%s board %s failed: %s", kind, token, exc)
        return jobs
