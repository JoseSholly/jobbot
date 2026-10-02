from datetime import datetime

from jobbot.domain.models import RawJob, Region
from jobbot.services.normalize import normalize


def test_normalize_cleans_fields_and_tags_region():
    job = normalize(
        RawJob(
            source="x",
            url="https://a.com/j/1/?utm_source=t",
            title=" <b>Backend Engineer</b> ",
            company="Acme &amp; Co",
            description="<p>Django</p>",
            location="Lagos, Nigeria",
            posted_at=datetime(2026, 9, 30),
        )
    )
    assert job is not None
    assert job.url == "https://a.com/j/1"
    assert job.title == "Backend Engineer"
    assert job.company == "Acme & Co"
    assert job.region is Region.NG
    assert job.remote is False
    assert job.posted_at.tzinfo is not None


def test_normalize_infers_remote_and_global():
    job = normalize(RawJob(source="x", url="https://a.com/2", title="Engineer", location="Remote"))
    assert job.remote is True
    assert job.region is Region.GLOBAL


def test_region_hint_wins_and_unusable_jobs_dropped():
    job = normalize(RawJob(source="x", url="https://a.com/3", title="Dev", region_hint=Region.NG))
    assert job.region is Region.NG
    assert normalize(RawJob(source="x", url="", title="No url")) is None
    assert normalize(RawJob(source="x", url="https://a.com/4", title="  ")) is None
