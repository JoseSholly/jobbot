import httpx
import respx

from jobbot.adapters.sources import hnhiring, jobicy, pythonjobs, remotive, workingnomads
from jobbot.domain.models import Profile
from jobbot.interfaces.sources import SearchContext
from jobbot.services.ingestion import build_search_context
from jobbot.services.normalize import normalize_all


def test_pythonjobs_rss(fixture_text):
    remote, onsite = pythonjobs.parse(fixture_text("pythonjobs.xml"))
    assert (remote.title, remote.company) == ("Senior Django Developer", "Acme Analytics")
    assert remote.remote is True and "Remote" in remote.location
    assert onsite.remote is False and onsite.location.startswith("Berlin")
    assert remote.posted_at.day == 2


def test_workingnomads(fixture_json):
    [job] = workingnomads.parse(fixture_json("workingnomads.json"))
    assert (job.title, job.company, job.location) == ("Backend Python Engineer", "Zeta", "Europe, Africa")
    assert "fastapi" in job.description and job.posted_at is not None


def test_hn_thread_keeps_labelled_remote_posts(fixture_json):
    jobs = hnhiring.parse_thread(fixture_json("hn_thread.json"))
    assert len(jobs) == 1
    [job] = jobs
    assert job.company == "Acme AI"
    assert job.title.startswith("Senior Python Engineer")
    assert job.location == "REMOTE (Worldwide)"
    assert job.url == "https://news.ycombinator.com/item?id=45000001"
    assert normalize_all(jobs)[0].remote is True


def test_search_context_includes_top_skills():
    a = Profile(target_titles=["Backend Engineer"], skills=["Python", "Django", "FastAPI", "Redis"])
    b = Profile(target_titles=["AI Engineer"], skills=["python", "LangChain"])
    ctx = build_search_context([a, b], max_keywords=5, max_skills=3)
    assert ctx.skills == ["Python", "Django", "LangChain"]  # shared first, then by importance


@respx.mock
async def test_hn_fetch_finds_latest_thread(fixture_json):
    respx.get(hnhiring.SEARCH).mock(
        return_value=httpx.Response(
            200,
            json={
                "hits": [
                    {"title": "Ask HN: Who wants to be hired? (October 2026)", "objectID": "1"},
                    {"title": "Ask HN: Who is hiring? (October 2026)", "objectID": "45000000"},
                ]
            },
        )
    )
    respx.get(hnhiring.ITEM.format(id=45000000)).mock(
        return_value=httpx.Response(200, json=fixture_json("hn_thread.json"))
    )
    async with httpx.AsyncClient() as client:
        jobs = await hnhiring.HNHiringSource(client).fetch(SearchContext())
    assert len(jobs) == 1


@respx.mock
async def test_jobicy_searches_top_skills(fixture_json):
    route = respx.get(jobicy.URL).mock(return_value=httpx.Response(200, json=fixture_json("jobicy.json")))
    async with httpx.AsyncClient() as client:
        src = jobicy.JobicySource(client, {"count": 100, "max_tags": 2})
        await src.fetch(SearchContext(skills=["Python", "Django", "FastAPI"]))
    tags = [c.request.url.params.get("tag") for c in route.calls]
    assert tags == [None, "python", "django"]


@respx.mock
async def test_remotive_queries_each_category(fixture_json):
    route = respx.get(remotive.URL).mock(return_value=httpx.Response(200, json=fixture_json("remotive.json")))
    async with httpx.AsyncClient() as client:
        jobs = await remotive.RemotiveSource(client, {"categories": ["software-dev", "data"]}).fetch(
            SearchContext()
        )
    assert [c.request.url.params["category"] for c in route.calls] == ["software-dev", "data"]
    assert len(jobs) == 4
