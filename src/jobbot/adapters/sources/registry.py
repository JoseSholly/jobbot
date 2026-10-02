"""Build the list of enabled sources from config. Add new sources here."""

from __future__ import annotations

import httpx

from jobbot.adapters.sources.arbeitnow import ArbeitnowSource
from jobbot.adapters.sources.ats import ATSSource
from jobbot.adapters.sources.base import BaseSource
from jobbot.adapters.sources.himalayas import HimalayasSource
from jobbot.adapters.sources.jobberman import JobbermanSource
from jobbot.adapters.sources.jobicy import JobicySource
from jobbot.adapters.sources.jooble import JoobleSource
from jobbot.adapters.sources.myjobmag import MyJobMagSource
from jobbot.adapters.sources.remoteok import RemoteOKSource
from jobbot.adapters.sources.remotive import RemotiveSource
from jobbot.adapters.sources.weworkremotely import WeWorkRemotelySource
from jobbot.config import Settings

SOURCE_CLASSES: dict[str, type[BaseSource]] = {
    "remotive": RemotiveSource,
    "remoteok": RemoteOKSource,
    "himalayas": HimalayasSource,
    "arbeitnow": ArbeitnowSource,
    "jobicy": JobicySource,
    "weworkremotely": WeWorkRemotelySource,
    "jooble": JoobleSource,
    "myjobmag": MyJobMagSource,
    "jobberman": JobbermanSource,
    "ats": ATSSource,
}
SCRAPERS = {"myjobmag", "jobberman"}


def build_sources(
    settings: Settings, client: httpx.AsyncClient, only: set[str] | None = None
) -> list[BaseSource]:
    sources: list[BaseSource] = []
    scraper_delay = float(settings.http.get("scraper_delay_seconds", 2.0))
    for name, cls in SOURCE_CLASSES.items():
        if only is not None:
            if name not in only:
                continue
        elif not settings.source_enabled(name):
            continue
        kwargs = {
            "options": settings.source_options(name),
            "delay_seconds": scraper_delay if name in SCRAPERS else 0.0,
        }
        if cls is JoobleSource:
            kwargs["api_key"] = settings.secrets.jooble_api_key
        sources.append(cls(client, **kwargs))
    return sources
