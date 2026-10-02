"""RawJob -> Job: clean HTML, unify fields, decide remote + region."""

from __future__ import annotations

from datetime import UTC, datetime

from jobbot.domain.models import Job, RawJob, Region
from jobbot.domain.regions import is_nigerian
from jobbot.domain.text import canonical_url, contains_term, job_id_for, strip_html

MAX_DESCRIPTION_CHARS = 6000
_REMOTE_TERMS = ["remote", "work from home", "wfh", "anywhere", "distributed"]


def normalize(raw: RawJob) -> Job | None:
    """Return a clean Job, or None if the posting is unusable (no title/URL)."""
    url = canonical_url(raw.url)
    title = strip_html(raw.title)
    if not url or not title:
        return None
    description = strip_html(raw.description)[:MAX_DESCRIPTION_CHARS]
    location = strip_html(raw.location)

    remote = raw.remote
    if remote is None:
        haystack = f"{title} {location}".lower()
        remote = any(contains_term(haystack, t) for t in _REMOTE_TERMS)

    if raw.region_hint is not None:
        region = raw.region_hint
    elif is_nigerian(location):
        region = Region.NG
    else:
        region = Region.GLOBAL

    posted_at = raw.posted_at
    if posted_at is not None and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)

    return Job(
        id=job_id_for(url),
        source=raw.source,
        url=url,
        title=title,
        company=strip_html(raw.company) or "Unknown company",
        description=description,
        location=location or ("Remote" if remote else ""),
        remote=bool(remote),
        region=region,
        posted_at=posted_at,
    )


def normalize_all(raws: list[RawJob]) -> list[Job]:
    return [job for raw in raws if (job := normalize(raw)) is not None]


def utcnow() -> datetime:
    return datetime.now(UTC)
