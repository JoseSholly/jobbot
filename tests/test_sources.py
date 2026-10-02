import httpx
import pytest
import respx

from jobbot.adapters.sources import (
    arbeitnow,
    ats,
    himalayas,
    jobberman,
    jobicy,
    jooble,
    myjobmag,
    remoteok,
    remotive,
    weworkremotely,
)
from jobbot.adapters.sources.base import parse_date
from jobbot.domain.models import Region
from jobbot.interfaces.sources import SearchContext
from jobbot.services.normalize import normalize_all


def test_remotive(fixture_json):
    jobs = remotive.parse(fixture_json("remotive.json"))
    assert [j.title for j in jobs] == ["Senior Python Engineer", "Frontend Developer"]
    assert jobs[0].company == "Acme &amp; Co"  # cleaned later by normalize
    assert normalize_all(jobs)[0].company == "Acme & Co"
    assert jobs[0].posted_at.year == 2026


def test_remoteok_skips_legal_notice(fixture_json):
    jobs = remoteok.parse(fixture_json("remoteok.json"))
    assert len(jobs) == 1 and jobs[0].title == "Backend Engineer (Go)"
    assert jobs[0].location == "Worldwide"


def test_himalayas(fixture_json):
    [j] = himalayas.parse(fixture_json("himalayas.json"))
    assert j.location == "Nigeria, Kenya" and j.company == "Delta"


def test_arbeitnow_jobicy_wwr(fixture_json, fixture_text):
    [a] = arbeitnow.parse(fixture_json("arbeitnow.json"))
    assert a.remote is False and a.location == "Berlin"
    [b] = jobicy.parse(fixture_json("jobicy.json"))
    assert b.location == "EMEA" and b.posted_at is not None
    [c] = weworkremotely.parse(fixture_text("wwr.xml"))
    assert (c.company, c.title) == ("Eta Labs", "Senior Backend Developer")
    assert c.posted_at.day == 29


def test_jooble_tags_nigeria(fixture_json):
    jobs = jooble.parse(fixture_json("jooble.json"))
    assert jobs[0].region_hint is Region.NG
    assert jobs[1].region_hint is Region.NG  # empty location = searched in Nigeria
    assert jobs[0].posted_at is not None


def test_ats_parsers(fixture_json):
    [g] = ats.parse_greenhouse(fixture_json("greenhouse.json"), "kappa")
    assert g.remote is True and g.company == "Kappa"
    [lv] = ats.parse_lever(fixture_json("lever.json"), "lambda")
    assert normalize_all([lv])[0].region is Region.NG
    jobs = ats.parse_ashby(fixture_json("ashby.json"), "mu")
    assert [j.title for j in jobs] == ["Data Scientist"]


def test_scrapers(fixture_text):
    [m] = myjobmag.parse(fixture_text("myjobmag.html"))
    assert (m.title, m.company) == ("Backend Developer", "Nu Tech Limited")
    assert m.url == "https://www.myjobmag.com/job/backend-developer-nu-tech"
    assert m.region_hint is Region.NG
    [jb] = jobberman.parse(fixture_text("jobberman.html"))
    assert (jb.title, jb.company, jb.location) == ("Python Developer", "Xi Solutions", "Lagos")


def test_scraper_fallback_on_changed_markup():
    html = '<div><a href="/job/data-analyst-at-foo">Data Analyst at Foo</a></div>'
    [m] = myjobmag.parse(html)
    assert (m.title, m.company) == ("Data Analyst", "Foo")


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-30T00:00:00.0000000",
        "2026-09-28 09:15:00",
        "Tue, 29 Sep 2026 14:00:00 +0000",
        1790000000,
        1790000000000,
        "2026-09-27T10:00:00-04:00",
    ],
)
def test_parse_date_formats(value):
    assert parse_date(value) is not None


def test_parse_date_garbage():
    assert parse_date("yesterday-ish") is None
    assert parse_date(None) is None


@respx.mock
async def test_jooble_fetch_queries_each_keyword(fixture_json):
    route = respx.post("https://jooble.org/api/KEY").mock(
        return_value=httpx.Response(200, json=fixture_json("jooble.json"))
    )
    async with httpx.AsyncClient() as client:
        src = jooble.JoobleSource(client, {"pages_per_keyword": 1}, api_key="KEY")
        jobs = await src.fetch(SearchContext(keywords=["python", "django"]))
    assert route.call_count == 2
    assert len(jobs) == 4


@respx.mock
async def test_himalayas_paginates_until_short_page(fixture_json):
    respx.get(himalayas.URL).mock(return_value=httpx.Response(200, json=fixture_json("himalayas.json")))
    async with httpx.AsyncClient() as client:
        jobs = await himalayas.HimalayasSource(client, {"max_pages": 5}).fetch(SearchContext())
    assert len(jobs) == 1


@respx.mock
async def test_retry_on_503_then_success(fixture_json):
    route = respx.get(remotive.URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=fixture_json("remotive.json"))]
    )
    async with httpx.AsyncClient() as client:
        jobs = await remotive.RemotiveSource(client).fetch(SearchContext())
    assert route.call_count == 2 and len(jobs) == 2
