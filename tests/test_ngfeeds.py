import httpx
import respx

from jobbot.adapters.sources import ngfeeds
from jobbot.domain.models import Region
from jobbot.interfaces.sources import SearchContext
from jobbot.services.normalize import normalize_all


def test_parse_rss_tags_nigeria_and_splits_company(fixture_text):
    jobs = ngfeeds.parse_feed(fixture_text("hotnigerianjobs.xml"), "ng:hotnigerianjobs")
    assert [(j.title, j.company) for j in jobs] == [
        ("Backend Developer (Python / Django)", "Kuda Technologies"),
        ("Software Engineer", "Remote First Co"),
    ]
    assert jobs[0].location == "Lagos, Nigeria" and jobs[0].posted_at.day == 4
    assert jobs[1].remote is True
    assert all(j.region is Region.NG for j in normalize_all(jobs))


def test_parse_atom(fixture_text):
    [job] = ngfeeds.parse_feed(fixture_text("atom_jobs.xml"), "ng:x")
    assert (job.title, job.company, job.location) == ("AI Engineer", "Abuja Labs", "Abuja, Nigeria")
    assert job.url == "https://jobs.example.ng/ai-engineer"


def test_discover_feed_by_link_text(fixture_text):
    html = fixture_text("myjobmag_feeds_page.html")
    page = "https://www.myjobmag.com/feeds/"
    assert ngfeeds.discover_feed(html, page, "Detailed RSS") == "https://www.myjobmag.com/rss/detailed.xml"
    assert ngfeeds.discover_feed(html, page) == "https://www.myjobmag.com/rss/summary.xml"
    assert ngfeeds.discover_feed("<html>no feeds</html>", page) is None


@respx.mock
async def test_fetch_follows_feeds_page_and_isolates_failures(fixture_text):
    respx.get("https://www.myjobmag.com/feeds/").mock(
        return_value=httpx.Response(200, text=fixture_text("myjobmag_feeds_page.html"))
    )
    respx.get("https://www.myjobmag.com/rss/detailed.xml").mock(
        return_value=httpx.Response(200, text=fixture_text("hotnigerianjobs.xml"))
    )
    respx.get("https://broken.example/rss").mock(return_value=httpx.Response(404))
    options = {
        "feeds": [
            {"name": "myjobmag", "url": "https://www.myjobmag.com/feeds/", "link_text": "Detailed RSS"},
            {"name": "broken", "url": "https://broken.example/rss"},
        ]
    }
    async with httpx.AsyncClient() as client:
        jobs = await ngfeeds.NigerianFeedsSource(client, options).fetch(SearchContext())
    assert len(jobs) == 2 and jobs[0].source == "ng:myjobmag"
