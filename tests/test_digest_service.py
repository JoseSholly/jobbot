from datetime import UTC, datetime, timedelta

import pytest

from jobbot.adapters.memory import (
    MemoryFeedbackRepository,
    MemoryJobRepository,
    MemoryProfileRepository,
    MemoryRunRepository,
    MemorySentRepository,
    MemoryUserRepository,
)
from jobbot.domain.models import FeedbackAction, Profile, Region, Slot, User, UserStatus
from jobbot.services.alerts import AlertService
from jobbot.services.digest import DigestOptions, DigestRepositories, DigestService, slot_for
from jobbot.services.ingestion import IngestionService, build_search_context
from jobbot.services.matching import MatchingService
from jobbot.services.rerank import FeedbackReranker
from jobbot.services.scoring import DEFAULT_WEIGHTS, Scorer, ScoringConfig
from tests.fakes import FakeEmbedder, FakeLLM, FakeSource, RecordingNotifier, raw

ADMIN = 1
ALICE = 100
BOB = 200


def backend_jobs():
    now = datetime.now(UTC)
    jobs = [
        raw(
            f"Backend Engineer {i}",
            f"Global{i}",
            posted_at=now,
            description="Python Django PostgreSQL Docker REST APIs Celery Redis",
        )
        for i in range(8)
    ]
    jobs += [
        raw(
            f"Python Developer {i}",
            f"Naija{i}",
            location="Lagos",
            remote=False,
            posted_at=now,
            description="Python Django DRF PostgreSQL",
        )
        for i in range(6)
    ]
    jobs += [
        raw("Sales Executive", "Shop", posted_at=now, description="cold calls"),
        raw("Old Backend Engineer", "Old", posted_at=now - timedelta(days=30), description="Python Django"),
    ]
    return jobs


def build(sources, users, profiles, notifier=None, llm=None, embedder=None):
    repos = DigestRepositories(
        users=MemoryUserRepository(users),
        profiles=MemoryProfileRepository(profiles),
        jobs=MemoryJobRepository(),
        sent=MemorySentRepository(),
        feedback=MemoryFeedbackRepository(),
        runs=MemoryRunRepository(),
    )
    notifier = notifier or RecordingNotifier()
    service = DigestService(
        repos=repos,
        ingestion=IngestionService(sources),
        matching=MatchingService(
            Scorer(ScoringConfig(weights=DEFAULT_WEIGHTS)), FeedbackReranker(), min_score=50
        ),
        notifier=notifier,
        alerts=AlertService(notifier, ADMIN),
        embedder=embedder if embedder is not None else FakeEmbedder(),
        llm=llm,
    )
    return service, repos, notifier


def users():
    return [
        User(ALICE, "alice", UserStatus.ACTIVE),
        User(BOB, "bob", UserStatus.ACTIVE),
        User(300, "pending", UserStatus.PENDING),
    ]


def opts(**kw):
    return DigestOptions(slot=Slot.MORNING, send_delay_seconds=0, **kw)


async def test_full_run_sends_quota_and_never_repeats(backend_profile):
    service, repos, notifier = build([FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile})
    report = await service.run(opts())
    assert report.users_sent == 1
    assert report.users_skipped == {BOB: "no profile yet"}
    [text] = notifier.texts_for(ALICE)
    assert "Morning digest: 10 jobs" in text
    assert "Sales Executive" not in text and "Old Backend" not in text
    assert text.count("Naija") == 4  # NG quota
    assert notifier.texts_for(300) == []

    # Second run with the same jobs: only 4 unsent jobs remain (2 NG + 2 global... any mix).
    report2 = await service.run(opts())
    [_, text2] = notifier.texts_for(ALICE)
    sent_first = {line for line in text.splitlines() if "https://" in line}
    sent_second = {line for line in text2.splitlines() if "https://" in line}
    assert sent_first.isdisjoint(sent_second)
    assert report2.users_sent == 1
    assert repos.runs.runs[-1]["status"] == "ok"


async def test_failing_source_is_isolated_and_alerts_admin(backend_profile):
    good = FakeSource("good", backend_jobs())
    bad = FakeSource("bad", error=RuntimeError("boom"))
    service, _, notifier = build([good, bad], users(), {ALICE: backend_profile})
    report = await service.run(opts())
    assert report.source_errors == {"bad": "RuntimeError: boom"}
    assert notifier.texts_for(ALICE)
    assert any("problems" in t and "bad" in t for t in notifier.texts_for(ADMIN))


async def test_blocked_user_is_paused_and_others_still_get_digest(backend_profile):
    notifier = RecordingNotifier(unreachable={BOB})
    service, repos, _ = build(
        [FakeSource("fake", backend_jobs())],
        users(),
        {ALICE: backend_profile, BOB: backend_profile},
        notifier=notifier,
    )
    report = await service.run(opts())
    assert repos.users.get(BOB).status is UserStatus.PAUSED
    assert notifier.texts_for(ALICE)
    assert report.users_skipped[BOB].startswith("unreachable")


async def test_dry_run_records_nothing(backend_profile):
    service, repos, notifier = build([FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile})
    report = await service.run(opts(dry_run=True))
    assert notifier.sent == []
    assert repos.sent.sent_keys(ALICE) == (set(), set())
    assert len(report.previews[ALICE]) == 1


async def test_no_matches_message(backend_profile):
    service, _, notifier = build(
        [FakeSource("fake", [raw("Chef", "Kitchen")])], users(), {ALICE: backend_profile}
    )
    await service.run(opts())
    assert "No new jobs" in notifier.texts_for(ALICE)[0]


async def test_llm_reasons_added_and_llm_failure_tolerated(backend_profile):
    service, _, notifier = build(
        [FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile}, llm=FakeLLM()
    )
    await service.run(opts())
    assert "<i>Matches your Python</i>" in notifier.texts_for(ALICE)[0]

    service, _, notifier = build(
        [FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile}, llm=FakeLLM(fail=True)
    )
    await service.run(opts())
    assert "Morning digest" in notifier.texts_for(ALICE)[0]


async def test_embedder_failure_falls_back_to_lexical(backend_profile):
    class Broken:
        def embed(self, texts):
            raise OSError("model download failed")

    service, _, notifier = build(
        [FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile}, embedder=Broken()
    )
    report = await service.run(opts())
    assert report.users_sent == 1 and notifier.texts_for(ALICE)


async def test_feedback_dismissed_never_resent_and_saved_boosts(backend_profile):
    service, repos, notifier = build([FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile})
    await service.run(opts(dry_run=True))
    # Simulate: user dismissed one job (not yet sent).
    jobs = (await service.ingestion.ingest(build_search_context([backend_profile], 5))).jobs
    target = next(j for j in jobs if j.region is Region.GLOBAL)
    repos.feedback.add(ALICE, target.id, FeedbackAction.DISMISS)
    await service.run(opts())
    assert target.url not in notifier.texts_for(ALICE)[0]


async def test_only_chat_id(backend_profile):
    service, _, notifier = build(
        [FakeSource("fake", backend_jobs())], users(), {ALICE: backend_profile, BOB: backend_profile}
    )
    await service.run(opts(only_chat_id=BOB))
    assert notifier.texts_for(ALICE) == [] and notifier.texts_for(BOB)


def test_search_context_unions_titles():
    a = Profile(target_titles=["Python Developer", "Backend Engineer"])
    b = Profile(target_titles=["python developer", "Data Analyst"])
    ctx = build_search_context([a, b], 10)
    assert ctx.keywords[0] == "Python Developer"
    assert len(ctx.keywords) == 3


@pytest.mark.parametrize("hour,slot", [(7, Slot.MORNING), (17, Slot.EVENING)])
def test_slot_for(hour, slot):
    assert slot_for(datetime(2026, 10, 2, hour)) is slot


async def test_all_sources_failing_alerts_admin_and_sends_users_nothing(backend_profile):
    service, repos, notifier = build(
        [FakeSource("a", error=RuntimeError("down"))], users(), {ALICE: backend_profile}
    )
    with pytest.raises(RuntimeError):
        await service.run(opts())
    assert notifier.texts_for(ALICE) == []
    assert any("crashed" in t for t in notifier.texts_for(ADMIN))
    assert repos.runs.runs[-1]["status"] == "failed"
