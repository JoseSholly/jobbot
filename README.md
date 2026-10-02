# JobBot

A free, serverless Telegram bot that reads each user's CV, finds matching jobs in Nigeria and worldwide, and sends **10 jobs at 07:00 and 10 at 17:00 (WAT)**, so 20 a day. It is multi-user, invite-only, and costs **$0** to run.

- **Matching:** a semantic match between your CV and each job (local `all-MiniLM-L6-v2` embeddings), plus skill overlap, title fit and recency.
- **Sources:** Remotive, RemoteOK, Himalayas, Arbeitnow, Jobicy, We Work Remotely, Jooble (Nigeria), Greenhouse/Lever/Ashby company boards, and optional MyJobMag and Jobberman scrapers.
- **Mix:** 4 Nigerian and 6 international jobs per digest by default. Each user can change this with `/split`.
- **No repeats:** a job is never sent to the same person twice, even when it appears on several boards.
- **Buttons under every job:** 💾 save · ✖ not for me (future digests re-rank away from it) · ✍ tailored CV bullets (Gemini).
- **Self-serve onboarding:** `/start`, then an invite code or admin approval, then send your CV as a PDF. The bot builds your profile and DMs it back.

```
            Telegram users
                 │  messages, CV uploads, button taps
                 ▼
   Cloudflare Worker (webhook, TypeScript) ─── workflow_dispatch ──┐
     onboarding · commands · feedback · tailor                    │
                 │                                                 ▼
                 ▼                                GitHub Actions (Python, uv)
           Neon Postgres  ◀───────────────────────  build_profile.yml  (on CV upload)
   users · profiles · sent · feedback · jobs        digest.yml         (cron 06:00 & 16:00 UTC)
                                                     fetch → normalize → dedupe → embed once
                                                     → per user: filter → score → re-rank → quota → send
```

---

## Contents
- [Prerequisites](#prerequisites)
- [Setup (step by step)](#setup-step-by-step)
- [Using the bot](#using-the-bot)
- [Local development](#local-development)
- [Project structure](#project-structure)
- [How matching works](#how-matching-works)
- [Configuration](#configuration)
- [Testing](#testing)
- [Costs & limits](#costs--limits)
- [Privacy](#privacy)
- [Troubleshooting](#troubleshooting)
- More docs: [architecture](docs/architecture.md) · [setup in detail](docs/setup.md) · [configuration](docs/configuration.md) · [sources](docs/sources.md) · [worker](docs/worker.md) · [operations](docs/operations.md)

---

## Prerequisites

All of these are free.

| # | What | Why | Where |
|---|---|---|---|
| 1 | **Telegram bot token** | The bot itself | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| 2 | **Your Telegram chat ID** | Makes you the admin | Message [@userinfobot](https://t.me/userinfobot), or call `getUpdates` (see [setup](docs/setup.md#2-find-your-chat-id)) |
| 3 | **Neon Postgres** database | Stores users, profiles and history | [neon.tech](https://neon.tech) → new project → copy the **pooled** connection string |
| 4 | **Cloudflare account** | Hosts the webhook Worker | [dash.cloudflare.com](https://dash.cloudflare.com) (free plan) |
| 5 | **GitHub fine-grained token** | Lets the Worker start the profile-build workflow | GitHub → Settings → Developer settings → Fine-grained tokens → this repo only → **Actions: Read and write** |
| 6 | **Jooble API key** | Main source of Nigerian jobs | [jooble.org/api/about](https://jooble.org/api/about) |
| 7 | **Gemini API key** *(optional, recommended)* | Better CV parsing, "why it matches" lines, ✍ tailored bullets | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |

Tools: [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python), Node.js 20+ (for deploying the Worker), git.

---

## Setup (step by step)

The short version is below. [docs/setup.md](docs/setup.md) has every click and command.

**1. Clone and install**
```bash
git clone https://github.com/JoseSholly/jobbot && cd jobbot
uv sync                       # installs Python 3.12 + all dependencies from uv.lock
cp .env.example .env          # fill in your values
```

**2. Create the database schema** (in your Neon database)
```bash
uv run jobbot-migrate
uv run jobbot-admin bootstrap     # makes ADMIN_CHAT_ID an active admin
uv run jobbot-admin send-test     # you should get a Telegram message
```

**3. Add GitHub repository secrets** (Settings → Secrets and variables → Actions)

`TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `DATABASE_URL`, `JOOBLE_API_KEY`, `GEMINI_API_KEY` (optional)

**4. Deploy the Worker**
```bash
cd worker && npm ci
npx wrangler login
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET        # any long random string, e.g. `openssl rand -hex 32`
npx wrangler secret put DATABASE_URL
npx wrangler secret put ADMIN_CHAT_ID
npx wrangler secret put GITHUB_TOKEN          # the fine-grained PAT
npx wrangler secret put GEMINI_API_KEY        # optional
npx wrangler deploy                           # prints https://jobbot.<you>.workers.dev
```
Edit `GITHUB_REPO` and `GITHUB_REF` in `worker/wrangler.toml` if your fork or default branch differs.

**5. Point Telegram at the Worker**
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://jobbot.<you>.workers.dev/telegram" \
  -d "secret_token=<WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]'
```

**6. Merge to the default branch.** Scheduled workflows and `workflow_dispatch` only run from the default branch.

**7. Try it.** Send `/start` to your bot, then send your CV as a PDF. About 2 minutes later you'll get your profile. To get a digest straight away, open **Actions → Digest → Run workflow**.

**8. Invite people.** Send `/invite 5 14` to the bot (5 uses, valid 14 days) and share the code. Anyone who `/start`s without a code shows up for you with Approve and Reject buttons.

---

## Using the bot

| Command | What it does |
|---|---|
| `/start [code]` | Join (with an invite code) or request access |
| `/join CODE` | Redeem an invite code (sending just the code also works) |
| *send a PDF* | Upload or replace your CV; your profile is rebuilt automatically |
| `/profile` | Show your matching profile |
| `/titles a, b` | Set the job titles to search for |
| `/skills add a, b` · `remove a` · `set …` | Edit skills |
| `/exclude add a` · `remove a` · `set …` | Words that disqualify a job (e.g. `unpaid`, `PHP`) |
| `/locations Nigeria, Worldwide, Africa, EMEA` | Where you can work. Remote jobs restricted elsewhere are skipped |
| `/seniority mid, senior` | Your levels |
| `/remote on\|off` | Include remote jobs |
| `/summary …` | A 2–3 sentence description of you, used for semantic matching |
| `/split 4 6` | Nigerian vs international jobs per digest (each 0–10, total up to 10) |
| `/saved` | Jobs you saved with 💾 |
| `/pause` · `/resume` | Stop or restart digests |
| `/delete` | Permanently delete your account and data |
| **Admin:** `/invite [uses] [days]`, `/users`, `/approve ID`, `/block ID` | Access control |

A new CV replaces the CV-derived fields (titles, skills, seniority, summary). Your location, remote and exclusion preferences are kept.

---

## Local development

```bash
uv sync                                    # deps + dev tools (pytest, ruff, respx)

# No database needed: build a profile from your CV, then dry-run a digest for it
uv run jobbot-build-profile --pdf ~/cv.pdf --out profile.json   # review/edit profile.json
uv run jobbot-digest --dry-run --profile-file profile.json      # prints the digest

# Against your database (reads .env)
uv run jobbot-digest --dry-run                 # everyone, printed not sent
uv run jobbot-digest --user 123456789          # really send to one user
uv run jobbot-digest --sources remotive,jobicy --no-reasons -v
```

| CLI | Purpose |
|---|---|
| `jobbot-digest` | Run a digest (`--slot`, `--dry-run`, `--user`, `--profile-file`, `--sources`, `--no-reasons`) |
| `jobbot-build-profile` | CV → profile (`--chat-id` for an uploaded CV, `--pdf` for a local file) |
| `jobbot-migrate` | Create or upgrade the schema (idempotent) |
| `jobbot-admin` | `bootstrap`, `invite`, `users`, `approve`/`pause`/`block`, `send-test` |

Worker: `cd worker && npm ci && npm run typecheck && npm test`. Run `npx wrangler dev` for a local server ([docs/worker.md](docs/worker.md)).

---

## Project structure

The code is built in layers so that business logic never depends on a specific API, database or vendor ([architecture](docs/architecture.md)):

```
src/jobbot/
  domain/        Pure data + rules: Job, Profile, regions, text helpers. No I/O.
  interfaces/    Protocols (ports): JobSource, *Repository, Notifier, Embedder, LLMClient
  services/      Business logic. Depends only on domain + interfaces.
    ingestion.py   fetch all sources concurrently, isolated → normalize → dedupe
    filters.py     hard rules (age, already sent, excluded words, location)
    scoring.py     0–100 score (semantic/skills/title/recency)
    rerank.py      feedback-based re-ranking from 💾/✖
    selection.py   Nigeria/global quota with fill-from-other-side
    matching.py    filters → score → re-rank, per user
    digest.py      orchestrates a whole run for all users
    profile.py     CV → profile (Gemini or heuristic), keeps user prefs
    formatting.py  Telegram HTML, escaping, 4096-char splitting, buttons
    users.py, alerts.py, cv_parser.py, normalize.py, dedupe.py
  adapters/      Concrete implementations of the interfaces
    sources/       one module per job board + registry.py
    db/            Postgres (Neon) repositories + migrations runner
    memory.py      in-memory repositories (local runs and tests)
    telegram.py, gemini.py, embedder.py (fastembed), pdf.py, http.py
  container.py   Composition root: the only place that picks adapters
  entrypoints/   Thin CLIs (digest, build_profile, migrate, admin)
worker/src/      Cloudflare Worker: handlers → services → repositories/clients
migrations/      SQL schema shared by Python and the Worker
tests/           pytest: unit tests with fakes + Postgres integration tests
```

**Adding a job source:** write `adapters/sources/<name>.py` with a pure `parse()` function and a `fetch()` class, register it in `adapters/sources/registry.py`, add `<name>: {enabled: true}` to `config.yaml`, and add a fixture plus a parser test. See [docs/sources.md](docs/sources.md#adding-a-source).

---

## How matching works

1. **Fetch once per run.** All sources are fetched concurrently. One failing source is logged and skipped, and the admin is alerted.
2. **Normalize and dedupe.** HTML is stripped, tracking parameters are removed from URLs, and each job is tagged `NG` or `GLOBAL`. Duplicates by URL, or by company + title, are merged.
3. **Embed once.** Every job is embedded once with `all-MiniLM-L6-v2` on CPU (ONNX through `fastembed`, no PyTorch needed).
4. **Per user:**
   - **Filter:** the job is ≤ 14 days old, never sent to this user (by id *or* company + title), not dismissed, contains no excluded words, and its location fits (a Nigerian job, or a remote job open to the user's `/locations`).
   - **Score (0–100):** 60% semantic similarity + 25% skill overlap + 10% title match + 5% recency.
   - **Re-rank:** ±10 points by similarity to the jobs you saved or dismissed.
   - **Select:** best 4 NG + 6 global, with empty slots filled from the other side. Anything under 50 is dropped.
   - **Explain (optional):** Gemini writes one short "why it matches" line per job.
5. **Send and remember.** Each job is recorded in `sent` so it never repeats. History is pruned after 60 days.

Every weight and threshold is in [`config.yaml`](config.yaml).

---

## Configuration

- **Secrets** come from environment variables: `.env` locally, GitHub secrets in Actions, `wrangler secret` for the Worker. See [`.env.example`](.env.example).
- **Behaviour** lives in [`config.yaml`](config.yaml): quotas, minimum score, weights, retention, Gemini model, and which sources are on, with their options (WWR feeds, ATS company boards, scraper toggles).
- **Worker settings** live in [`worker/wrangler.toml`](worker/wrangler.toml) `[vars]`: `MAX_USERS`, default split, GitHub repo and branch, Gemini model.

Every option is described in [docs/configuration.md](docs/configuration.md).

---

## Testing

```bash
uv run pytest                     # unit tests (fakes, fixtures, mocked HTTP)
uv run ruff check src tests && uv run ruff format --check src tests

# include the Postgres integration tests
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/jobbot_test uv run pytest

cd worker && npm run typecheck && TEST_DATABASE_URL=... npm test
```
CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs all of the above against a Postgres service container.

---

## Costs & limits

| Resource | Free allowance | JobBot usage |
|---|---|---|
| GitHub Actions (private repo) | 2,000 min/month | about 3–5 min per digest × 60, plus about 1 min per CV ≈ 250–350 min |
| Cloudflare Workers | 100k requests/day | one request per message or button tap |
| Neon | 0.5 GB storage | a few MB for dozens of users |
| Gemini free tier | rate-limited per minute and day | 1 call per user per digest + 1 per CV + 1 per ✍ tap. Capped by `max_reason_users_per_run` |

GitHub cron can start 5–30 minutes late. Use **Run workflow** if a digest is missing. A public repo gets unlimited Actions minutes, and no user data lives in the repo.

---

## Privacy

- CVs, profiles and history live only in **your** Neon database, never in git. `.gitignore` blocks `*.pdf`, `.env` and `profile.json`.
- With `GEMINI_API_KEY` set, CV text and job descriptions are sent to Google's Gemini API. On the free tier, Google may use that data to improve its products. Tell your users (the bot shows a privacy note when someone joins), or leave the key unset to use the local heuristic parser.
- `/delete` removes a user and, by cascade, their profile, CV text, sent history and feedback.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Bot doesn't reply | Check the webhook with `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`. The URL must end in `/telegram`, and `last_error_message` shows the error. Make sure `WEBHOOK_SECRET` matches. |
| "Got your CV, but I couldn't start processing" | Check `GITHUB_TOKEN` (fine-grained, this repo, Actions read & write) and `GITHUB_REPO`/`GITHUB_REF` in `wrangler.toml`. The workflow must exist on that branch. |
| Profile never arrives | Look at **Actions → Build profile** logs. Scanned (image-only) PDFs have no text, so export a text PDF. |
| No digest | Look at **Actions → Digest** logs and the `runs` table. The user must be `active` and have a profile. |
| "No new jobs above your match threshold" | Broaden `/titles` and `/skills`, or lower `digest.min_score`. |
| A source keeps failing | It's isolated, so other sources still work. Disable it in `config.yaml` and check [docs/sources.md](docs/sources.md). |

More in [docs/operations.md](docs/operations.md).
