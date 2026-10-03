# Cloudflare Worker

The Worker is the bot's always-on half. It receives Telegram webhooks at `POST /telegram`, checks the `X-Telegram-Bot-Api-Secret-Token` header against `WEBHOOK_SECRET`, answers `200` immediately, and processes the update in `ctx.waitUntil` so Telegram never retries because of a slow database or LLM call.

## Layout
```
worker/src/
  index.ts               HTTP entry: auth, parse, hand off to the router
  container.ts           buildServices(env): wires clients + repositories into services
  handlers/
    router.ts            message vs document vs button; private chats only
    commands.ts          command table (public / member / admin)
    callbacks.ts         a:/r: approve/reject, s:/d:/t: save/dismiss/tailor, del: delete
  services/              business rules; return Reply objects, never call Telegram directly
    userService.ts       /start, invites, approvals, MAX_USERS, pause/resume, /split, delete
    profileService.ts    /profile, /titles, /skills, /exclude, /locations, /seniority, /remote, /summary
    cvService.ts         validate PDF → save file_id → dispatch build_profile.yml
    feedbackService.ts   💾/✖ (only for jobs actually sent to that user), /saved
    tailorService.ts     ✍ tailored CV bullets with Gemini (strict "no invention" prompt)
    messages.ts          help text, profile rendering
  repositories/          SQL against the shared schema (users, invites, profiles, jobs, feedback)
  clients/               Telegram, GitHub (workflow_dispatch), Gemini
  db.ts                  Sql port + Neon HTTP implementation
```

## Commands for development
```bash
cd worker
npm ci
npm run typecheck
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/jobbot_test npm test
npx wrangler dev          # local server on :8787; put secrets in worker/.dev.vars (gitignored)
npx wrangler deploy
npx wrangler tail         # live logs from production
```

To try the deployed webhook by hand:
```bash
curl -X POST https://jobbot.<you>.workers.dev/telegram \
  -H "x-telegram-bot-api-secret-token: $WEBHOOK_SECRET" -H 'content-type: application/json' \
  -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":<ADMIN_CHAT_ID>,"type":"private"},"from":{"id":<ADMIN_CHAT_ID>},"text":"/help"}}'
```

## Cron Trigger (on-time digests)
`wrangler.toml` declares `[triggers] crons = ["0 6 * * *", "0 16 * * *"]`. At those times (UTC) the Worker's `scheduled` handler calls `ScheduleService.triggerDigest`. That service dispatches `digest.yml` with `{slot, trigger: "cloudflare"}`, retrying up to 3 times. If every attempt fails, or `GITHUB_TOKEN` is missing, the admin gets a Telegram alert.

Check that it's registered with `npx wrangler deployments list`, or in the dashboard under Workers → jobbot → Settings → Triggers. Test it locally with `npx wrangler dev --test-scheduled`, then `curl "http://localhost:8787/__scheduled?cron=0+6+*+*+*"`.

The workflow file must exist on the branch named by `GITHUB_REF` (default `main`).

## Security notes
- Requests without the right secret header get `401`.
- Only private chats are handled. Group messages are ignored.
- Admin commands and approve/reject buttons check `ADMIN_CHAT_ID`.
- Button actions on jobs check the `sent` table, so users can only act on jobs that were sent to them.
- Invite redemption is a single atomic `UPDATE … WHERE uses < max_uses AND not expired`.
- The GitHub token only needs **Actions: read & write** on this one repository.

## Free-plan limits
100,000 requests a day and 10 ms of CPU per request. Waiting on `fetch` (Neon, Telegram, Gemini) doesn't count as CPU, and `waitUntil` work can run up to 30 s after the response.
