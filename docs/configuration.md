# Configuration reference

There are three places for settings:

1. **Secrets** in environment variables: `.env` locally, GitHub Actions secrets, `wrangler secret`.
2. **Behaviour** in [`config.yaml`](../config.yaml), used by the Python jobs. Point to another file with `JOBBOT_CONFIG` or `--config`.
3. **Worker vars** in [`worker/wrangler.toml`](../worker/wrangler.toml).

## Environment variables

| Name | Used by | Required | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Python, Worker | yes | From @BotFather |
| `ADMIN_CHAT_ID` | Python, Worker | yes | Your chat id. Gets alerts, approval requests and admin commands |
| `DATABASE_URL` | Python, Worker | yes | Neon pooled connection string |
| `JOOBLE_API_KEY` | Python | recommended | Without it the Jooble source is skipped, and there's less Nigerian coverage |
| `GEMINI_API_KEY` | Python, Worker | optional | CV parsing, match reasons, ✍ tailoring |
| `WEBHOOK_SECRET` | Worker | yes | Random string. Must match `secret_token` in `setWebhook` |
| `GITHUB_TOKEN` | Worker | recommended | Fine-grained PAT, Actions read & write. Without it the admin is told to build profiles by hand |
| `FASTEMBED_CACHE_PATH` | Python | optional | Where the embedding model is cached |
| `JOBBOT_CONFIG` | Python | optional | Path to an alternative `config.yaml` |
| `TEST_DATABASE_URL` | tests | optional | Enables the Postgres integration tests. **Its schema is wiped.** |

## config.yaml

### `digest`
| Key | Default | Meaning |
|---|---|---|
| `timezone` | `Africa/Lagos` | Decides morning/evening when `--slot` isn't given (before 12:00 = morning) |
| `default_ng_quota` / `default_global_quota` | 4 / 6 | Split for new users (Python admin bootstrap; the Worker uses its own vars) |
| `min_score` | 50 | Jobs below this are never sent, even if that means fewer than 10 |
| `max_age_days` | 14 | Older postings are ignored. Postings without a date are kept |
| `send_delay_seconds` | 0.5 | Pause between users (Telegram allows about 30 msgs/s overall) |

### `scoring`
| Key | Default | Meaning |
|---|---|---|
| `weights.semantic/skills/title/recency` | .60/.25/.10/.05 | Must sum to 1.0 (checked at startup) |
| `semantic_floor` / `semantic_ceiling` | 0.15 / 0.65 | MiniLM cosine similarities mostly fall in this band and are mapped linearly to 0–1. Raise the floor if irrelevant jobs score too high |
| `skill_saturation` | 5 | Matching this many of the user's skills gives the full skill score |
| `feedback_max_adjust` | 10 | Maximum ± points from 💾/✖ history |
| `feedback_min_events` | 1 | Feedback events needed before re-ranking starts |

### Other sections
| Key | Default | Meaning |
|---|---|---|
| `embedding.model` | `sentence-transformers/all-MiniLM-L6-v2` | Any model `fastembed` supports |
| `retention.sent_days` | 60 | After this, a job could in theory be sent again (in practice it's too old by then) |
| `retention.jobs_days` | 90 | Cached job rows are pruned unless someone saved them |
| `llm.model` | `gemini-2.5-flash` | Gemini model for parsing and reasons |
| `llm.match_reasons` | true | Turns the one-line "why it matches" on or off |
| `llm.max_reason_users_per_run` | 50 | Users per run who get reasons (free-tier rate limits) |
| `search.max_keywords` | 12 | Distinct job titles (across all users) sent to query-based sources |
| `search.max_skills` | 4 | Top skills (across all users) used for skill searches (Jobicy tags) |
| `http.timeout_seconds` | 30 | Per request |
| `http.user_agent` | `JobBot/0.1 (+repo url)` | Sent to every source |
| `http.scraper_delay_seconds` | 2.0 | Delay between scraper requests |

### `sources`
Every source has `enabled`. Source-specific options:

| Source | Options |
|---|---|
| `himalayas` | `max_pages` (20 jobs per page) |
| `arbeitnow` | `max_pages` |
| `jobicy` | `count` (max 100) |
| `weworkremotely` | `feeds`: list of category RSS URLs |
| `remotive` | `categories`: Remotive category slugs (default `software-dev`, `data`) |
| `jobicy` | `max_tags`: how many top skills to search for |
| `jooble` | `host` (country site matching your key, e.g. `ng.jooble.org`), `pages_per_keyword` |
| `myjobmag`, `jobberman` | `pages_per_keyword`. **Off by default**, see [sources.md](sources.md) |
| `ats` | `greenhouse`, `lever`, `ashby`: lists of company board tokens |

## worker/wrangler.toml `[vars]`
| Var | Default | Meaning |
|---|---|---|
| `GITHUB_REPO` | `JoseSholly/jobbot` | Repo containing `build_profile.yml` |
| `GITHUB_REF` | `main` | Branch to run the workflow from |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model used for ✍ tailoring |
| `MAX_USERS` | 50 | Maximum **active** users. Invites and approvals are refused beyond it |
| `DEFAULT_NG_QUOTA` / `DEFAULT_GLOBAL_QUOTA` | 4 / 6 | Split for new users |
