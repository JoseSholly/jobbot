# Job sources

| Source | Module | Type | Auth | Region | Default |
|---|---|---|---|---|---|
| Remotive | `remotive.py` | JSON API | none | global remote | on |
| RemoteOK | `remoteok.py` | JSON API | none (User-Agent, link back) | global remote | on |
| Himalayas | `himalayas.py` | JSON API, paginated | none | global remote | on |
| Arbeitnow | `arbeitnow.py` | JSON API, paginated | none | EU, some remote | on |
| Jobicy | `jobicy.py` | JSON API | none | global remote | on |
| We Work Remotely | `weworkremotely.py` | RSS | none | global remote | on |
| Jooble | `jooble.py` | JSON API (POST) | `JOOBLE_API_KEY` | **Nigeria** | on (skipped without key) |
| Greenhouse / Lever / Ashby | `ats.py` | public board JSON | none | per company | on (list in config) |
| MyJobMag | `myjobmag.py` | HTML scraper | none | **Nigeria** | **off** |
| Jobberman | `jobberman.py` | HTML scraper | none | **Nigeria** | **off** |

Notes
- **Fetch once, share across users.** Feed-style sources ignore the search context. Query-style sources (Jooble and the scrapers) search for the union of all active users' `target_titles`, most common first, capped at `search.max_keywords`.
- **Nigeria vs global.** Jooble and the scrapers search in Nigeria and tag results `NG`. Any other job whose location mentions Nigeria or a Nigerian city is `NG` too. Everything else is `GLOBAL`, and it only counts if it's remote and open to the user's `/locations` (Worldwide, Africa, EMEA, Nigeria or no restriction).
- **Adzuna** is not used because it doesn't cover Nigeria.
- **LinkedIn** is not used (terms of service, and brittle).
- **Isolation.** Each source runs in its own try/except. A failure shows up in the run's stats and in the admin alert, and never stops the run.

## The Nigerian scrapers
MyJobMag and Jobberman have no public API. The scrapers:
- are **disabled by default**. Before enabling them, read each site's `robots.txt` and terms of use, and only enable them if scraping their search pages is allowed;
- wait `http.scraper_delay_seconds` (2 s) between requests, use a descriptive User-Agent, and fetch only `pages_per_keyword` pages per search term;
- parse forgivingly: known card selectors first, then a fallback that collects any link shaped like a job page. When the sites change their markup, expect to update the selectors. The fixtures in `tests/fixtures/*.html` show what the parser expects.

The selectors were written from the sites' known structure. They could not be checked against the live sites from the build environment, so do a test run with `--sources myjobmag,jobberman --dry-run -v` before turning them on.

## Company boards (ATS)
Add companies to `config.yaml`:
```yaml
ats:
  enabled: true
  greenhouse: [gitlab]       # boards.greenhouse.io/<token>
  lever: [somecompany]       # jobs.lever.co/<token>
  ashby: [anothercompany]    # jobs.ashbyhq.com/<token>
```
Unknown tokens are logged and skipped.

## Adding a source
1. Create `src/jobbot/adapters/sources/<name>.py`:
   ```python
   from jobbot.adapters.sources.base import BaseSource, parse_date
   from jobbot.domain.models import RawJob
   from jobbot.interfaces.sources import SearchContext

   URL = "https://example.com/api/jobs"

   def parse(payload: dict) -> list[RawJob]:          # pure: easy to test with a fixture
       return [RawJob(source="example", url=i["url"], title=i["title"],
                      company=i.get("company", ""), description=i.get("html", ""),
                      location=i.get("location", ""), remote=i.get("remote"),
                      posted_at=parse_date(i.get("published")))
               for i in payload["jobs"]]

   class ExampleSource(BaseSource):
       name = "example"

       async def fetch(self, ctx: SearchContext) -> list[RawJob]:
           return parse(await self.get_json(URL))     # retries + timeouts built in
   ```
2. Register it in `adapters/sources/registry.py` (`SOURCE_CLASSES`).
3. Add `example: {enabled: true}` under `sources:` in `config.yaml`.
4. Save a real response to `tests/fixtures/example.json` and add a parser test to `tests/test_sources.py`.

You don't need to clean HTML, canonicalize URLs, tag regions or dedupe. `services/normalize.py` and `services/dedupe.py` do that for every source.
