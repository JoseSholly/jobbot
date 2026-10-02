"""Contract every job source implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from jobbot.domain.models import RawJob


@dataclass(slots=True)
class SearchContext:
    """What we're looking for this run (union of all active users' interests).

    Feed-style sources (Remotive, RemoteOK, ...) ignore it; query-style sources
    (Jooble, Nigerian boards) use ``keywords`` to build searches.
    """

    keywords: list[str] = field(default_factory=list)
    nigeria_location: str = "Nigeria"


class JobSource(Protocol):
    name: str

    async def fetch(self, ctx: SearchContext) -> list[RawJob]: ...
