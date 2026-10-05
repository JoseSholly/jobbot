"""In-memory repositories. Used for local dry-runs without a database, and by tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jobbot.domain.models import FeedbackAction, Job, Profile, User


class MemoryUserRepository:
    def __init__(self, users: list[User] | None = None):
        self.users: dict[int, User] = {u.chat_id: u for u in users or []}

    def get(self, chat_id: int) -> User | None:
        return self.users.get(chat_id)

    def list_active(self) -> list[User]:
        return [u for u in self.users.values() if u.status == "active"]

    def list_all(self) -> list[User]:
        return list(self.users.values())

    def upsert(self, user: User) -> None:
        self.users[user.chat_id] = user

    def delete(self, chat_id: int) -> None:
        self.users.pop(chat_id, None)


class MemoryInviteRepository:
    def __init__(self) -> None:
        self.invites: dict[str, dict[str, Any]] = {}

    def create(self, code: str, created_by: int, max_uses: int, expires_at: datetime | None) -> None:
        self.invites[code] = {
            "created_by": created_by,
            "max_uses": max_uses,
            "uses": 0,
            "expires_at": expires_at,
        }


class MemoryProfileRepository:
    def __init__(self, profiles: dict[int, Profile] | None = None):
        self.profiles: dict[int, Profile] = dict(profiles or {})
        self.cv_file_ids: dict[int, str] = {}
        self.cv_texts: dict[int, str] = {}

    def get(self, chat_id: int) -> Profile | None:
        return self.profiles.get(chat_id)

    def get_cv_file_id(self, chat_id: int) -> str | None:
        return self.cv_file_ids.get(chat_id)

    def get_cv_text(self, chat_id: int) -> str | None:
        return self.cv_texts.get(chat_id)

    def list_with_cv(self) -> list[int]:
        return sorted(c for c, text in self.cv_texts.items() if text)

    def save(self, chat_id: int, profile: Profile, cv_text: str | None = None) -> None:
        self.profiles[chat_id] = profile
        if cv_text is not None:
            self.cv_texts[chat_id] = cv_text


class MemoryJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.embeddings: dict[str, list[float]] = {}

    def upsert_many(self, jobs: list[Job], embeddings: dict[str, list[float]]) -> None:
        for job in jobs:
            self.jobs[job.id] = job
            if job.id in embeddings:
                self.embeddings[job.id] = embeddings[job.id]

    def get_embeddings(self, job_ids: list[str]) -> dict[str, list[float]]:
        return {i: self.embeddings[i] for i in job_ids if i in self.embeddings}

    def prune(self, older_than_days: int) -> int:
        return 0


class MemorySentRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, tuple[str, datetime, float]]] = {}

    def sent_keys(self, chat_id: int) -> tuple[set[str], set[str]]:
        rows = self.rows.get(chat_id, {})
        return set(rows), {key for key, _, _ in rows.values()}

    def record(self, chat_id: int, jobs: list[tuple[Job, float]]) -> None:
        now = datetime.now(UTC)
        bucket = self.rows.setdefault(chat_id, {})
        for job, score in jobs:
            bucket[job.id] = (job.dedupe_key, now, score)

    def prune(self, older_than_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        removed = 0
        for bucket in self.rows.values():
            for job_id in [j for j, (_, at, _) in bucket.items() if at < cutoff]:
                del bucket[job_id]
                removed += 1
        return removed


class MemoryFeedbackRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, FeedbackAction]] = {}

    def add(self, chat_id: int, job_id: str, action: FeedbackAction) -> None:
        self.rows.setdefault(chat_id, {})[job_id] = action

    def job_ids_by_action(self, chat_id: int) -> dict[FeedbackAction, list[str]]:
        out: dict[FeedbackAction, list[str]] = {a: [] for a in FeedbackAction}
        for job_id, action in self.rows.get(chat_id, {}).items():
            out[action].append(job_id)
        return out


class MemoryRunRepository:
    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []

    def start(self, slot: str) -> int:
        self.runs.append({"slot": slot, "status": "running", "started_at": datetime.now(UTC)})
        return len(self.runs)

    def finish(self, run_id: int, status: str, stats: dict[str, Any], error: str | None) -> None:
        self.runs[run_id - 1].update(status=status, stats=stats, error=error)

    def delivered_since(self, slot: str, since: datetime) -> bool:
        return any(
            r["slot"] == slot and r["status"] in ("ok", "partial") and r["started_at"] >= since
            for r in self.runs
        )
