"""Core domain objects. Pure data: no I/O, no framework imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Region(StrEnum):
    NG = "NG"
    GLOBAL = "GLOBAL"


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"


class FeedbackAction(StrEnum):
    SAVE = "save"
    DISMISS = "dismiss"


class Slot(StrEnum):
    MORNING = "morning"
    EVENING = "evening"


@dataclass(slots=True)
class Job:
    """A normalized job posting, regardless of which source it came from."""

    id: str
    source: str
    url: str
    title: str
    company: str
    description: str
    location: str
    remote: bool
    region: Region
    posted_at: datetime | None

    @property
    def dedupe_key(self) -> str:
        from jobbot.domain.text import normalize_key

        return f"{normalize_key(self.company)}|{normalize_key(self.title)}"

    @property
    def embedding_text(self) -> str:
        return f"{self.title}. {self.description[:1500]}"


@dataclass(slots=True)
class RawJob:
    """What a source returns before normalization (fields may be messy/HTML)."""

    source: str
    url: str
    title: str
    company: str = ""
    description: str = ""
    location: str = ""
    remote: bool | None = None
    posted_at: datetime | None = None
    region_hint: Region | None = None  # set by Nigeria-only sources


@dataclass(slots=True)
class Profile:
    """A user's matching profile, parsed from their CV and hand-editable."""

    target_titles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    remote_ok: bool = True
    countries_ok: list[str] = field(default_factory=lambda: ["Nigeria", "Worldwide", "Africa", "EMEA"])
    exclude_keywords: list[str] = field(default_factory=list)
    summary: str = ""
    # Broader/adjacent titles recruiters actually post ("Python Developer", "Virtual Assistant").
    # Used to widen searches and title matching beyond target_titles.
    related_titles: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)  # industries, e.g. fintech, e-commerce

    @property
    def all_titles(self) -> list[str]:
        seen: set[str] = set()
        out = []
        for title in [*self.target_titles, *self.related_titles]:
            if title.lower() not in seen:
                seen.add(title.lower())
                out.append(title)
        return out

    @property
    def embedding_text(self) -> str:
        parts = [self.summary, "Roles: " + ", ".join(self.all_titles)]
        if self.skills:
            parts.append("Skills: " + ", ".join(self.skills))
        if self.domains:
            parts.append("Industries: " + ", ".join(self.domains))
        return ". ".join(p for p in parts if p.strip())

    def to_dict(self) -> dict:
        return {
            "target_titles": self.target_titles,
            "skills": self.skills,
            "seniority": self.seniority,
            "remote_ok": self.remote_ok,
            "countries_ok": self.countries_ok,
            "exclude_keywords": self.exclude_keywords,
            "summary": self.summary,
            "related_titles": self.related_titles,
            "domains": self.domains,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> Profile:
        data = data or {}
        default = cls()

        def str_list(key: str, fallback: list[str]) -> list[str]:
            value = data.get(key)
            if not isinstance(value, list):
                return fallback
            return [str(v).strip() for v in value if str(v).strip()]

        return cls(
            target_titles=str_list("target_titles", []),
            skills=str_list("skills", []),
            seniority=str_list("seniority", []),
            remote_ok=bool(data.get("remote_ok", True)),
            countries_ok=str_list("countries_ok", default.countries_ok),
            exclude_keywords=str_list("exclude_keywords", []),
            summary=str(data.get("summary") or ""),
            related_titles=str_list("related_titles", []),
            domains=str_list("domains", []),
        )

    @property
    def is_usable(self) -> bool:
        return bool(self.target_titles or self.skills or self.summary)


@dataclass(slots=True)
class User:
    chat_id: int
    username: str | None
    status: UserStatus
    ng_quota: int = 4
    global_quota: int = 6
    is_admin: bool = False


@dataclass(slots=True)
class ScoreBreakdown:
    semantic: float
    skills: float
    title: float
    recency: float
    feedback: float = 0.0

    def total(self, weights: dict[str, float]) -> float:
        base = 100 * (
            weights["semantic"] * self.semantic
            + weights["skills"] * self.skills
            + weights["title"] * self.title
            + weights["recency"] * self.recency
        )
        return max(0.0, min(100.0, base + self.feedback))


@dataclass(slots=True)
class ScoredJob:
    job: Job
    score: float
    breakdown: ScoreBreakdown
    reason: str | None = None


@dataclass(slots=True)
class SentRecord:
    job_id: str
    dedupe_key: str
    sent_at: datetime
