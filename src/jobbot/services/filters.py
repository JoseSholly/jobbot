"""Hard rules a job must pass before it is scored for a user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from jobbot.domain.models import Job, Profile, Region
from jobbot.domain.regions import location_allows
from jobbot.domain.text import contains_term


@dataclass(slots=True)
class FilterContext:
    now: datetime
    max_age_days: int
    sent_ids: set[str]
    sent_keys: set[str]
    dismissed_ids: set[str]


def reject_reason(job: Job, profile: Profile, ctx: FilterContext) -> str | None:
    """Return why the job is rejected, or None if it passes. Handy for debugging."""
    if job.id in ctx.sent_ids or job.dedupe_key in ctx.sent_keys:
        return "already_sent"
    if job.id in ctx.dismissed_ids:
        return "dismissed"
    if job.posted_at is not None and job.posted_at < ctx.now - timedelta(days=ctx.max_age_days):
        return "too_old"
    haystack = f"{job.title} {job.company} {job.description}".lower()
    for keyword in profile.exclude_keywords:
        if contains_term(haystack, keyword):
            return "excluded_keyword"
    if not location_ok(job, profile):
        return "location"
    return None


def location_ok(job: Job, profile: Profile) -> bool:
    if job.region is Region.NG:
        return True
    if job.remote:
        return profile.remote_ok and location_allows(job.location, profile.countries_ok)
    # On-site / hybrid outside Nigeria: only if the user explicitly lists that place.
    explicit = [c for c in profile.countries_ok if c.lower() not in {"worldwide", "anywhere", "global"}]
    return bool(job.location) and location_allows(job.location, explicit)


def apply_filters(jobs: list[Job], profile: Profile, ctx: FilterContext) -> list[Job]:
    return [job for job in jobs if reject_reason(job, profile, ctx) is None]
