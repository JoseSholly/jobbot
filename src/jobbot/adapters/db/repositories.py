"""Concrete repositories implementing jobbot.interfaces.repositories on Postgres."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from jobbot.adapters.db.pool import Database
from jobbot.domain.models import FeedbackAction, Job, Profile, User, UserStatus


def _user(row: dict) -> User:
    return User(
        chat_id=row["chat_id"],
        username=row["username"],
        status=UserStatus(row["status"]),
        ng_quota=row["ng_quota"],
        global_quota=row["global_quota"],
        is_admin=row["is_admin"],
    )


class PgUserRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, chat_id: int) -> User | None:
        row = self.db.connection().execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,)).fetchone()
        return _user(row) if row else None

    def list_active(self) -> list[User]:
        rows = (
            self.db.connection()
            .execute("SELECT * FROM users WHERE status = 'active' ORDER BY chat_id")
            .fetchall()
        )
        return [_user(r) for r in rows]

    def list_all(self) -> list[User]:
        rows = self.db.connection().execute("SELECT * FROM users ORDER BY chat_id").fetchall()
        return [_user(r) for r in rows]

    def upsert(self, user: User) -> None:
        self.db.connection().execute(
            """
            INSERT INTO users (chat_id, username, status, is_admin, ng_quota, global_quota)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (chat_id) DO UPDATE SET
              username = COALESCE(EXCLUDED.username, users.username),
              status = EXCLUDED.status, is_admin = EXCLUDED.is_admin,
              ng_quota = EXCLUDED.ng_quota, global_quota = EXCLUDED.global_quota,
              updated_at = now()
            """,
            (user.chat_id, user.username, user.status.value, user.is_admin, user.ng_quota, user.global_quota),
        )

    def delete(self, chat_id: int) -> None:
        self.db.connection().execute("DELETE FROM users WHERE chat_id = %s", (chat_id,))


class PgInviteRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, code: str, created_by: int, max_uses: int, expires_at: datetime | None) -> None:
        self.db.connection().execute(
            "INSERT INTO invites (code, created_by, max_uses, expires_at) VALUES (%s, %s, %s, %s)",
            (code, created_by, max_uses, expires_at),
        )


class PgProfileRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, chat_id: int) -> Profile | None:
        row = (
            self.db.connection()
            .execute("SELECT data FROM profiles WHERE chat_id = %s", (chat_id,))
            .fetchone()
        )
        if not row or not row["data"]:
            return None
        return Profile.from_dict(row["data"])

    def get_cv_file_id(self, chat_id: int) -> str | None:
        row = (
            self.db.connection()
            .execute("SELECT cv_file_id FROM profiles WHERE chat_id = %s", (chat_id,))
            .fetchone()
        )
        return row["cv_file_id"] if row else None

    def save(self, chat_id: int, profile: Profile, cv_text: str | None = None) -> None:
        self.db.connection().execute(
            """
            INSERT INTO profiles (chat_id, data, cv_text, built_at)
            VALUES (%s, %s, %s, CASE WHEN %s::text IS NULL THEN NULL ELSE now() END)
            ON CONFLICT (chat_id) DO UPDATE SET
              data = EXCLUDED.data,
              cv_text = COALESCE(EXCLUDED.cv_text, profiles.cv_text),
              built_at = COALESCE(EXCLUDED.built_at, profiles.built_at),
              updated_at = now()
            """,
            (chat_id, Jsonb(profile.to_dict()), cv_text, cv_text),
        )

    def set_cv_file_id(self, chat_id: int, file_id: str) -> None:
        self.db.connection().execute(
            """
            INSERT INTO profiles (chat_id, cv_file_id) VALUES (%s, %s)
            ON CONFLICT (chat_id) DO UPDATE SET cv_file_id = EXCLUDED.cv_file_id, updated_at = now()
            """,
            (chat_id, file_id),
        )


class PgJobRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert_many(self, jobs: list[Job], embeddings: dict[str, list[float]]) -> None:
        if not jobs:
            return
        with self.db.transaction() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO jobs (id, source, url, title, company, description, location,
                                  remote, region, posted_at, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  embedding = COALESCE(EXCLUDED.embedding, jobs.embedding),
                  fetched_at = now()
                """,
                [
                    (
                        j.id,
                        j.source,
                        j.url,
                        j.title,
                        j.company,
                        j.description,
                        j.location,
                        j.remote,
                        j.region.value,
                        j.posted_at,
                        embeddings.get(j.id),
                    )
                    for j in jobs
                ],
            )

    def get_embeddings(self, job_ids: list[str]) -> dict[str, list[float]]:
        if not job_ids:
            return {}
        rows = (
            self.db.connection()
            .execute(
                "SELECT id, embedding FROM jobs WHERE id = ANY(%s) AND embedding IS NOT NULL",
                (job_ids,),
            )
            .fetchall()
        )
        return {r["id"]: list(r["embedding"]) for r in rows}

    def prune(self, older_than_days: int) -> int:
        cur = self.db.connection().execute(
            """
            DELETE FROM jobs j
            WHERE j.fetched_at < now() - make_interval(days => %s)
              AND NOT EXISTS (SELECT 1 FROM feedback f WHERE f.job_id = j.id AND f.action = 'save')
            """,
            (older_than_days,),
        )
        return cur.rowcount


class PgSentRepository:
    def __init__(self, db: Database):
        self.db = db

    def sent_keys(self, chat_id: int) -> tuple[set[str], set[str]]:
        rows = (
            self.db.connection()
            .execute("SELECT job_id, dedupe_key FROM sent WHERE chat_id = %s", (chat_id,))
            .fetchall()
        )
        return {r["job_id"] for r in rows}, {r["dedupe_key"] for r in rows}

    def record(self, chat_id: int, jobs: list[tuple[Job, float]]) -> None:
        if not jobs:
            return
        with self.db.transaction() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO sent (chat_id, job_id, dedupe_key, score) VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id, job_id) DO NOTHING
                """,
                [(chat_id, job.id, job.dedupe_key, score) for job, score in jobs],
            )

    def prune(self, older_than_days: int) -> int:
        cur = self.db.connection().execute(
            "DELETE FROM sent WHERE sent_at < now() - make_interval(days => %s)",
            (older_than_days,),
        )
        return cur.rowcount


class PgFeedbackRepository:
    def __init__(self, db: Database):
        self.db = db

    def job_ids_by_action(self, chat_id: int) -> dict[FeedbackAction, list[str]]:
        rows = (
            self.db.connection()
            .execute(
                "SELECT job_id, action FROM feedback WHERE chat_id = %s ORDER BY created_at DESC LIMIT 500",
                (chat_id,),
            )
            .fetchall()
        )
        out: dict[FeedbackAction, list[str]] = {a: [] for a in FeedbackAction}
        for r in rows:
            out[FeedbackAction(r["action"])].append(r["job_id"])
        return out


class PgRunRepository:
    def __init__(self, db: Database):
        self.db = db

    def start(self, slot: str) -> int:
        row = (
            self.db.connection()
            .execute("INSERT INTO runs (slot) VALUES (%s) RETURNING id", (slot,))
            .fetchone()
        )
        return row["id"]

    def finish(self, run_id: int, status: str, stats: dict[str, Any], error: str | None) -> None:
        self.db.connection().execute(
            "UPDATE runs SET status = %s, stats = %s, error = %s, finished_at = now() WHERE id = %s",
            (status, Jsonb(stats), error, run_id),
        )
