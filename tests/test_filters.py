from datetime import UTC, datetime, timedelta

from jobbot.domain.models import Region
from jobbot.services.filters import FilterContext, reject_reason
from tests.fakes import job

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def ctx(**kw):
    base = dict(now=NOW, max_age_days=14, sent_ids=set(), sent_keys=set(), dismissed_ids=set())
    base.update(kw)
    return FilterContext(**base)


def test_passes_good_job(backend_profile):
    assert reject_reason(job(posted_at=NOW), backend_profile, ctx()) is None


def test_rejects_old(backend_profile):
    old = job(posted_at=NOW - timedelta(days=15))
    assert reject_reason(old, backend_profile, ctx()) == "too_old"


def test_unknown_date_is_kept(backend_profile):
    j = job()
    j.posted_at = None
    assert reject_reason(j, backend_profile, ctx()) is None


def test_rejects_already_sent_by_id_or_key(backend_profile):
    j = job(posted_at=NOW)
    assert reject_reason(j, backend_profile, ctx(sent_ids={j.id})) == "already_sent"
    same_elsewhere = job(posted_at=NOW, url="https://other.example/x")
    assert reject_reason(same_elsewhere, backend_profile, ctx(sent_keys={j.dedupe_key})) == "already_sent"


def test_rejects_dismissed_and_excluded(backend_profile):
    j = job(posted_at=NOW)
    assert reject_reason(j, backend_profile, ctx(dismissed_ids={j.id})) == "dismissed"
    php = job("PHP Developer", posted_at=NOW)
    assert reject_reason(php, backend_profile, ctx()) == "excluded_keyword"
    intern = job("Backend Internship", posted_at=NOW)
    assert reject_reason(intern, backend_profile, ctx()) == "excluded_keyword"


def test_location_rules(backend_profile):
    us_only = job(location="USA Only", posted_at=NOW)
    assert reject_reason(us_only, backend_profile, ctx()) == "location"
    lagos_onsite = job(location="Lagos", remote=False, posted_at=NOW)
    assert lagos_onsite.region is Region.NG
    assert reject_reason(lagos_onsite, backend_profile, ctx()) is None
    berlin_onsite = job(location="Berlin", remote=False, posted_at=NOW)
    assert reject_reason(berlin_onsite, backend_profile, ctx()) == "location"


def test_remote_not_ok_rejects_global_remote(backend_profile):
    backend_profile.remote_ok = False
    assert reject_reason(job(posted_at=NOW), backend_profile, ctx()) == "location"


def test_level_words_only_exclude_by_title(backend_profile):
    backend_profile.exclude_keywords = ["junior", "intern", "internship", "graduate", "unpaid"]
    mentor = job(
        "Senior Backend Engineer",
        posted_at=NOW,
        description="You will mentor junior engineers and run our internship program.",
    )
    assert reject_reason(mentor, backend_profile, ctx()) is None
    assert (
        reject_reason(job("Junior Python Developer", posted_at=NOW), backend_profile, ctx())
        == "excluded_keyword"
    )
    unpaid = job("Backend Engineer", posted_at=NOW, description="This is an unpaid role.")
    assert reject_reason(unpaid, backend_profile, ctx()) == "excluded_keyword"
