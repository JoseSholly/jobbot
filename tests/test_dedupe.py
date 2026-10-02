from datetime import UTC, datetime

from jobbot.services.dedupe import dedupe
from tests.fakes import job


def test_same_url_is_deduped():
    a = job("Python Developer", url="https://x.com/1?utm_source=a")
    b = job("Python Developer", url="https://x.com/1")
    assert len(dedupe([a, b])) == 1


def test_same_company_and_title_across_sources_keeps_richest():
    short = job("Senior Engineer", "Acme Ltd", url="https://a.com/1", description="short")
    rich = job(
        "Senior Engineer (Remote)",
        "ACME",
        url="https://b.com/2",
        description="a much longer and richer description " * 5,
    )
    result = dedupe([short, rich])
    assert len(result) == 1
    assert result[0].url == "https://b.com/2"


def test_different_jobs_survive():
    jobs = [job("Python Developer", "A"), job("Python Developer", "B"), job("Go Developer", "A")]
    assert len(dedupe(jobs)) == 3


def test_dated_posting_preferred():
    undated = job("Dev", "A", url="https://a.com/1", description="x" * 100)
    undated.posted_at = None
    dated = job("Dev", "A", url="https://b.com/1", posted_at=datetime(2026, 9, 1, tzinfo=UTC))
    assert dedupe([undated, dated])[0].url == "https://b.com/1"
