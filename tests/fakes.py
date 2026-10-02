"""Test doubles for the interfaces in jobbot.interfaces.*."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import numpy as np

from jobbot.domain.models import Job, Profile, RawJob, Region
from jobbot.domain.text import tokens
from jobbot.interfaces.notifier import OutgoingMessage, RecipientUnavailable
from jobbot.interfaces.sources import SearchContext


def raw(
    title: str,
    company: str = "Acme",
    *,
    url: str | None = None,
    location: str = "Worldwide",
    remote: bool | None = True,
    description: str = "",
    posted_at: datetime | None = None,
    region_hint: Region | None = None,
    source: str = "fake",
) -> RawJob:
    slug = hashlib.md5(f"{title}{company}".encode()).hexdigest()[:8]
    return RawJob(
        source=source,
        url=url or f"https://jobs.example.com/{slug}",
        title=title,
        company=company,
        description=description or title,
        location=location,
        remote=remote,
        posted_at=posted_at or datetime.now(UTC),
        region_hint=region_hint,
    )


def job(title: str = "Python Developer", company: str = "Acme", **kwargs) -> Job:
    from jobbot.services.normalize import normalize

    result = normalize(raw(title, company, **kwargs))
    assert result is not None
    return result


class FakeSource:
    def __init__(self, name: str, jobs: list[RawJob] | None = None, error: Exception | None = None):
        self.name = name
        self.jobs = jobs or []
        self.error = error
        self.contexts: list[SearchContext] = []

    async def fetch(self, ctx: SearchContext) -> list[RawJob]:
        self.contexts.append(ctx)
        if self.error:
            raise self.error
        return list(self.jobs)


class FakeEmbedder:
    """Deterministic bag-of-words hashing embedder: similar words -> similar vectors."""

    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for tok in tokens(text):
                vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = np.linalg.norm(vec)
            out.append((vec / norm if norm else vec).tolist())
        return out


class RecordingNotifier:
    def __init__(self, unreachable: set[int] | None = None):
        self.sent: list[tuple[int, OutgoingMessage]] = []
        self.unreachable = unreachable or set()

    async def send(self, chat_id: int, message: OutgoingMessage) -> None:
        if chat_id in self.unreachable:
            raise RecipientUnavailable("Forbidden: bot was blocked by the user")
        self.sent.append((chat_id, message))

    def texts_for(self, chat_id: int) -> list[str]:
        return [m.text for c, m in self.sent if c == chat_id]


class FakeLLM:
    def __init__(self, profile: Profile | None = None, fail: bool = False):
        self.profile = profile
        self.fail = fail
        self.reason_calls = 0

    async def parse_cv(self, cv_text: str) -> Profile | None:
        if self.fail:
            raise RuntimeError("quota exceeded")
        return self.profile

    async def match_reasons(self, profile: Profile, jobs: list[Job]) -> list[str] | None:
        self.reason_calls += 1
        if self.fail:
            raise RuntimeError("quota exceeded")
        return [f"Matches your {profile.skills[0] if profile.skills else 'experience'}" for _ in jobs]


class FakeDownloader:
    def __init__(self, data: bytes = b"%PDF"):
        self.data = data

    async def download(self, file_id: str) -> bytes:
        return self.data


class FakeExtractor:
    def __init__(self, text: str):
        self.text = text

    def extract(self, data: bytes) -> str:
        return self.text
