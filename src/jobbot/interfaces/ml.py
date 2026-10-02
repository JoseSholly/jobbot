"""Embedding and LLM contracts. Both are optional at runtime (graceful fallbacks)."""

from __future__ import annotations

from typing import Protocol

from jobbot.domain.models import Job, Profile


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return L2-normalized vectors, one per text."""
        ...


class LLMClient(Protocol):
    async def parse_cv(self, cv_text: str) -> Profile | None: ...
    async def match_reasons(self, profile: Profile, jobs: list[Job]) -> list[str] | None: ...
