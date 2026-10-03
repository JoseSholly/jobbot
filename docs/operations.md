# Operations

## Schedules
| Workflow | When | Manual run |
|---|---|---|
| Digest | 06:00 and 16:00 UTC (07:00 / 17:00 WAT), started by the Worker's Cron Trigger. GitHub's own schedule is a late/unreliable backup, and the second trigger for a slot is skipped (`--once-per-slot`) | Actions → Digest → *Run workflow* (slot, single user, dry run). Manual runs always send |
| Build profile | Whenever a user uploads a CV (dispatched by the Worker) | Actions → Build profile → *Run workflow* with a chat_id |
| CI | Every push and PR | n/a |

## Monitoring
- **Telegram alerts** go to `ADMIN_CHAT_ID` when a source fails, a user's delivery fails, every source fails, or a workflow crashes.
- **`runs` table:** one row per digest, with `status` (`ok` / `partial` / `failed`), per-source counts and errors.
  ```sql
  SELECT id, slot, status, started_at, stats->'per_source' AS sources, stats->'source_errors' AS errors
  FROM runs ORDER BY id DESC LIMIT 10;
  ```
- **Useful queries**
  ```sql
  SELECT status, count(*) FROM users GROUP BY 1;
  SELECT chat_id, count(*) AS sent_last_7d FROM sent WHERE sent_at > now() - interval '7 days' GROUP BY 1;
  SELECT action, count(*) FROM feedback GROUP BY 1;
  ```

## Admin tasks
| Task | Telegram | Terminal |
|---|---|---|
| Invite | `/invite 5 14` | `uv run jobbot-admin invite --uses 5 --days 14` |
| List users | `/users` | `uv run jobbot-admin users` |
| Approve / block | buttons, `/approve ID`, `/block ID` | `uv run jobbot-admin approve ID` / `block ID` |
| Rebuild someone's profile | n/a | Actions → Build profile, or `uv run jobbot-build-profile --chat-id ID` |
| Resend a digest to one person | n/a | Actions → Digest → user = ID |

## Tuning relevance
- Too many irrelevant jobs: raise `digest.min_score` or `scoring.semantic_floor`, and add `/exclude` words.
- Too few jobs: lower `min_score`, broaden `/titles`, enable more sources or ATS boards.
- Not enough Nigerian jobs: check `JOOBLE_API_KEY`, consider enabling the scrapers (see [sources.md](sources.md)), and check the users' `/titles`, since they drive the Nigerian searches.
- Compare scores: `jobbot-digest --dry-run --user ID -v` prints what each user would get.

## Upgrading the schema
Add `migrations/002_<name>.sql`. The digest workflow runs `jobbot-migrate` before every run, and the migration is applied once (tracked in `schema_migrations`). The Worker needs no changes unless it uses the new columns.

## Rotating secrets
- Telegram token: `/revoke` in @BotFather, then update the GitHub secret, run `wrangler secret put TELEGRAM_BOT_TOKEN`, and call `setWebhook` again.
- GitHub PAT: create a new one, then `wrangler secret put GITHUB_TOKEN`.
- Neon password: reset it in Neon, then update `DATABASE_URL` in GitHub and the Worker.

## Backups
Neon keeps a point-in-time restore window on the free plan. For an extra copy: `pg_dump "$DATABASE_URL" > backup.sql`.
