# Architecture

## Components

| Component | Runtime | Responsibility |
|---|---|---|
| **Cloudflare Worker** (`worker/`) | Always on (webhook), TypeScript | Everything interactive: `/start`, invites, approvals, profile commands, CV upload, 💾/✖/✍ buttons |
| **Build profile** (`.github/workflows/build_profile.yml`) | GitHub Actions, on demand | Download the CV from Telegram → PDF text → profile (Gemini or heuristic) → save → DM the user |
| **Digest** (`.github/workflows/digest.yml`) | GitHub Actions, dispatched by the Worker's Cron Trigger at 06:00 and 16:00 UTC (GitHub's own cron is a backup) | Fetch jobs once, match per user, send, record |
| **Neon Postgres** | Managed | Shared state for both runtimes (`migrations/001_init.sql`) |

Why this split: Telegram needs an always-on HTTPS endpoint for instant replies and button taps, and a Worker does that for free. Embedding models and PDF parsing need real CPU and Python, which GitHub Actions provides for free. The two never call each other directly except through `workflow_dispatch`: CV uploaded → build profile, and the Worker's Cron Trigger → digest (GitHub's own scheduler is unreliable). Everything else goes through the database.

## Layers (Python)

```
entrypoints/  ──▶  container.py  ──▶  services/  ──▶  domain/ + interfaces/
                        │                                  ▲
                        └──────────▶  adapters/  ──────────┘ (implement the interfaces)
```

- **domain/**: dataclasses (`Job`, `RawJob`, `Profile`, `User`, `ScoredJob`) and pure rules (`regions.py`, `text.py`). It imports nothing from the other layers.
- **interfaces/**: `typing.Protocol` ports: `JobSource`, `UserRepository`, `ProfileRepository`, `JobRepository`, `SentRepository`, `FeedbackRepository`, `RunRepository`, `InviteRepository`, `Notifier`, `FileDownloader`, `Embedder`, `LLMClient`.
- **services/**: the business logic. Services receive their collaborators through the constructor and only know the interfaces. Most of them are plain functions or small classes that are trivial to unit-test:
  - `IngestionService` runs the sources concurrently, catches errors per source, then normalizes and dedupes.
  - `MatchingService` composes `filters` → `Scorer` → `FeedbackReranker` → `selection`.
  - `DigestService` orchestrates a run: audience → ingest → embed once → per-user match → optional LLM reasons → render → send → record → prune → run log → alerts.
  - `ProfileService` turns CV text into a profile and merges it with existing preferences.
  - `UserService` handles admin bootstrap, invites and status changes. `AlertService` sends messages to the admin.
- **adapters/**: concrete I/O: one module per job source, Postgres repositories (psycopg 3), in-memory repositories, Telegram, Gemini, fastembed and pypdf.
- **container.py**: the **only** module that chooses implementations (Postgres or memory, Telegram or console). Swapping a vendor means changing one adapter and one line here.
- **entrypoints/**: argument parsing and nothing else.

Tests build services directly with fakes (`tests/fakes.py`, `adapters/memory.py`), so no network or database is needed for the core logic.

## Layers (Worker)

```
index.ts ─▶ handlers/router.ts ─▶ handlers/{commands,callbacks}.ts ─▶ services/* ─▶ repositories/* ─▶ db.ts (Sql port)
                                                                          └──────▶ clients/{telegram,github,gemini}.ts
container.ts wires everything (buildServices)
```

Services return `Reply` objects instead of calling Telegram, and the router sends them. That keeps the services pure enough to test against a real Postgres with a fake Telegram (`worker/test/integration.test.ts`). Repositories depend on the small `Sql` interface: Neon's HTTP driver in production, `pg` in tests.

## Data model

| Table | Written by | Read by | Notes |
|---|---|---|---|
| `users` | Worker (onboarding, `/split`, `/pause`), Python (auto-pause on block) | both | `status`: pending/active/paused/blocked |
| `invites` | Worker `/invite`, `jobbot-admin invite` | Worker | Redeemed atomically (`uses < max_uses`, not expired) |
| `profiles` | Worker (`cv_file_id`, edits), Python (parsed `data`, `cv_text`) | both | `data` JSONB matches `Profile.to_dict()` |
| `jobs` | Python (only jobs actually sent) | Worker (Tailor, `/saved`), Python (re-rank embeddings) | Pruned after 90 days unless saved |
| `sent` | Python | Python, Worker (authorizes button taps) | Per-user dedupe by `job_id` and `dedupe_key` |
| `feedback` | Worker (💾/✖) | Python re-ranker | One row per user per job, latest action wins |
| `runs` | Python | you | Status and per-source stats of every digest |

## Key flows

**Onboarding:** `/start` → `users` row (`pending`) → admin gets Approve/Reject buttons, *or* `/join CODE` → invite redeemed → `active` → "send your CV".

**CV upload:** the PDF arrives at the Worker → `profiles.cv_file_id` is set → `POST /repos/:repo/actions/workflows/build_profile.yml/dispatches {chat_id}` → the Action downloads the file via `getFile`, extracts text with pypdf, parses it with Gemini (falling back to the heuristic parser), saves the profile and DMs it.

**Digest:** Worker cron (06:00/16:00 UTC) dispatches `digest.yml` with `trigger=cloudflare`. GitHub's own schedule fires too, often late. Both are "automated", so they run `jobbot-digest --once-per-slot`, which exits immediately if the `runs` table already has an `ok`/`partial` run for that slot today (Africa/Lagos). Manual runs skip the check. Then `jobbot-migrate` (no-op when up to date) → `jobbot-digest` → for each active user with a profile: a message with one row of 💾 ✖ ✍ buttons per job. `callback_data` is `s:<job_id>` (16-hex id, well under Telegram's 64-byte cap).

**Buttons:** the Worker checks that the job was sent to *this* user (`sent`) before recording feedback or tailoring, so users can't act on arbitrary ids.

## Failure handling

| Failure | Behaviour |
|---|---|
| One source down or its HTML changed | Logged, other sources continue, admin alerted with the error |
| All sources down | Run aborts **before** messaging users (no misleading "no matches"), admin alerted, run marked `failed` |
| Embedding model unavailable | Falls back to lexical similarity for that run |
| Gemini error or quota | CV: heuristic parser. Reasons: line omitted. Tailor: "try again later" |
| User blocked the bot | Telegram 403 → user set to `paused`, others unaffected |
| Telegram 429 | Waits for `retry_after`, then retries |
| Workflow crash | `if: failure()` step sends the admin a link to the run |
