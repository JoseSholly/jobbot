"""Fetch every enabled source concurrently, in isolation, then normalize + dedupe."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from jobbot.domain.models import Job, Profile
from jobbot.interfaces.sources import JobSource, SearchContext
from jobbot.services.dedupe import dedupe
from jobbot.services.normalize import normalize_all

log = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    jobs: list[Job]
    per_source: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def all_failed(self) -> bool:
        return bool(self.errors) and not any(self.per_source.values())


def build_search_context(profiles: list[Profile], max_keywords: int) -> SearchContext:
    """Union of users' target titles, most common first (shared titles cost one query)."""
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for profile in profiles:
        for title in profile.target_titles:
            key = title.strip().lower()
            if key:
                counts[key] += 1
                display.setdefault(key, title.strip())
    keywords = [display[k] for k, _ in counts.most_common(max_keywords)]
    return SearchContext(keywords=keywords)


class IngestionService:
    def __init__(self, sources: list[JobSource]):
        self.sources = sources

    async def _run_one(self, source: JobSource, ctx: SearchContext):
        started = time.monotonic()
        try:
            raws = await source.fetch(ctx)
            log.info("source %s: %d jobs in %.1fs", source.name, len(raws), time.monotonic() - started)
            return source.name, raws, None
        except Exception as exc:  # isolate: one broken source never kills the run
            log.warning("source %s failed: %s", source.name, exc, exc_info=log.isEnabledFor(logging.DEBUG))
            return source.name, [], f"{type(exc).__name__}: {exc}"[:300]

    async def ingest(self, ctx: SearchContext) -> IngestionResult:
        results = await asyncio.gather(*(self._run_one(s, ctx) for s in self.sources))
        raws = []
        per_source: dict[str, int] = {}
        errors: dict[str, str] = {}
        for name, items, error in results:
            per_source[name] = len(items)
            raws.extend(items)
            if error:
                errors[name] = error
        jobs = dedupe(normalize_all(raws))
        log.info("ingested %d raw -> %d unique jobs", len(raws), len(jobs))
        return IngestionResult(jobs=jobs, per_source=per_source, errors=errors)
