"""Integration tests against a real Postgres. Skipped unless TEST_DATABASE_URL is set.

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/jobbot_test uv run pytest
"""

import os

import pytest

from jobbot.adapters.db.migrate import apply_migrations
from jobbot.adapters.db.pool import Database
from jobbot.adapters.db.repositories import (
    PgFeedbackRepository,
    PgInviteRepository,
    PgJobRepository,
    PgProfileRepository,
    PgRunRepository,
    PgSentRepository,
    PgUserRepository,
)
from jobbot.domain.models import FeedbackAction, Profile, User, UserStatus
from jobbot.services.users import UserService
from tests.fakes import job

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def db():
    database = Database(DSN)
    conn = database.connection()
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    assert apply_migrations(database) == ["001_init.sql"]
    assert apply_migrations(database) == []  # idempotent
    yield database
    database.close()


def test_users_profiles_sent_feedback_runs(db):
    users = PgUserRepository(db)
    users.upsert(User(1, "alice", UserStatus.ACTIVE))
    users.upsert(User(2, "bob", UserStatus.PENDING))
    assert [u.chat_id for u in users.list_active()] == [1]

    profiles = PgProfileRepository(db)
    profiles.set_cv_file_id(1, "FILE1")
    assert profiles.get(1) is None  # empty data until built
    profiles.save(1, Profile(skills=["Python"], target_titles=["Dev"]), cv_text="cv")
    assert profiles.get(1).skills == ["Python"]
    assert profiles.get_cv_file_id(1) == "FILE1"

    jobs = PgJobRepository(db)
    j1, j2 = job("Python Developer", "A"), job("Go Developer", "B")
    jobs.upsert_many([j1, j2], {j1.id: [0.1, 0.2]})
    jobs.upsert_many([j1], {})  # keeps existing embedding
    assert jobs.get_embeddings([j1.id, j2.id]) == {j1.id: pytest.approx([0.1, 0.2])}

    sent = PgSentRepository(db)
    sent.record(1, [(j1, 80.0), (j2, 70.0)])
    sent.record(1, [(j1, 80.0)])  # no duplicate error
    ids, keys = sent.sent_keys(1)
    assert ids == {j1.id, j2.id} and j1.dedupe_key in keys
    assert sent.prune(60) == 0

    db.connection().execute(
        "INSERT INTO feedback (chat_id, job_id, action) VALUES (1, %s, 'save'), (1, %s, 'dismiss')",
        (j1.id, j2.id),
    )
    actions = PgFeedbackRepository(db).job_ids_by_action(1)
    assert actions[FeedbackAction.SAVE] == [j1.id]
    assert actions[FeedbackAction.DISMISS] == [j2.id]

    runs = PgRunRepository(db)
    run_id = runs.start("morning")
    runs.finish(run_id, "ok", {"users": 1}, None)

    users.delete(1)  # cascades
    assert sent.sent_keys(1) == (set(), set())


def test_user_service_invites_and_admin(db):
    service = UserService(PgUserRepository(db), PgInviteRepository(db))
    admin = service.ensure_admin(99)
    assert admin.is_admin and admin.status is UserStatus.ACTIVE
    code = service.create_invite(99, max_uses=3)
    assert len(code) == 8
    row = db.connection().execute("SELECT * FROM invites WHERE code = %s", (code,)).fetchone()
    assert row["max_uses"] == 3 and row["expires_at"] is not None
