"""Remove duplicates inside one run (same URL, or same company + title)."""

from __future__ import annotations

from jobbot.domain.models import Job


def _quality(job: Job) -> tuple[int, int, float]:
    # Prefer postings with a date, then the richer description, then the newest.
    ts = job.posted_at.timestamp() if job.posted_at else 0.0
    return (1 if job.posted_at else 0, len(job.description), ts)


def dedupe(jobs: list[Job]) -> list[Job]:
    by_key: dict[str, Job] = {}
    seen_ids: dict[str, str] = {}  # job.id -> dedupe_key it was stored under
    for job in jobs:
        if job.id in seen_ids:
            key = seen_ids[job.id]
            if _quality(job) > _quality(by_key[key]):
                by_key[key] = job
            continue
        key = job.dedupe_key
        current = by_key.get(key)
        if current is None or _quality(job) > _quality(current):
            by_key[key] = job
        seen_ids[job.id] = key
    return list(by_key.values())
