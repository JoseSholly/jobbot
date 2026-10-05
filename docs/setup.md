# Setup in detail

This takes about 30–45 minutes the first time. Every service used is free.

## 1. Create the bot
1. In Telegram, open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Pick a name and a username ending in `bot`. Copy the **token** (`123456:ABC…`).
3. Optional: `/setdescription`, `/setuserpic`, and `/setcommands` with:
   ```
   start - Join or show status
   profile - Show your matching profile
   titles - Set job titles to search
   skills - add/remove/set skills
   exclude - add/remove words that disqualify a job
   locations - Where you can work
   split - Nigerian vs international jobs per digest
   saved - Jobs you saved
   pause - Pause digests
   resume - Resume digests
   help - All commands
   delete - Delete your data
   ```

## 2. Find your chat ID
Send any message to your new bot, then open
`https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and read `message.chat.id`.
(Before the webhook is set this works. Afterwards, use [@userinfobot](https://t.me/userinfobot).)
This number is `ADMIN_CHAT_ID`.

## 3. Neon database
1. Sign up at [neon.tech](https://neon.tech) and create a project (pick the region closest to you, e.g. Frankfurt).
2. On the dashboard, click **Connect** and copy the connection string with **Connection pooling** enabled.
   It looks like `postgresql://user:pass@ep-xxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
   This is `DATABASE_URL`, used by both Python and the Worker.

## 4. API keys
- **Jooble:** fill in the form on the **Nigeria** site, [ng.jooble.org/api/about](https://ng.jooble.org/api/about). Keys are per country, and a key from jooble.org only returns US jobs. The key arrives by email. Set it as `JOOBLE_API_KEY`.
- **Gemini (optional):** go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), click **Create API key**, and set it as `GEMINI_API_KEY`.

## 5. Local install and database bootstrap
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # if you don't have uv
git clone https://github.com/JoseSholly/jobbot && cd jobbot
uv sync
cp .env.example .env    # fill TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, DATABASE_URL, JOOBLE_API_KEY, GEMINI_API_KEY
uv run jobbot-migrate             # creates tables
uv run jobbot-admin bootstrap     # you become the active admin
uv run jobbot-admin send-test     # Telegram message "JobBot can reach you"
```

## 6. GitHub
1. **Secrets:** go to Settings → Secrets and variables → Actions → *New repository secret*, and add `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `DATABASE_URL`, `JOOBLE_API_KEY` and `GEMINI_API_KEY`.
2. **Token for the Worker:** go to your avatar → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → *Generate new token*.
   - Repository access: *Only select repositories* → `jobbot`
   - Permissions → Repository → **Actions: Read and write** (Metadata: read is added automatically)
   - Copy the token. This is `GITHUB_TOKEN` for the Worker. Set an expiry reminder.
3. **Default branch:** merge this code into the default branch (usually `main`). GitHub only runs `schedule` and `workflow_dispatch` workflows that exist there.
4. **Actions enabled:** check Settings → Actions → General → *Allow all actions*.

## 7. Cloudflare Worker
```bash
cd worker
npm ci
npx wrangler login                     # opens a browser
# check [vars] in wrangler.toml: GITHUB_REPO (owner/repo), GITHUB_REF (default branch), MAX_USERS
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET     # e.g. output of: openssl rand -hex 32
npx wrangler secret put DATABASE_URL
npx wrangler secret put ADMIN_CHAT_ID
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put GEMINI_API_KEY     # optional
npx wrangler deploy
```
Open the printed URL in a browser. You should see "JobBot worker is running."

## 8. Connect Telegram to the Worker
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://jobbot.<your-subdomain>.workers.dev/telegram" \
  -d "secret_token=<WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]'
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"     # check: no last_error_message
```

## 9. First run
1. Send `/start` to the bot. As admin you're active straight away.
2. Send your CV as a **PDF**. Within about 2 minutes you get "✅ Profile ready". If not, check Actions → *Build profile*.
3. Fix anything with `/titles`, `/skills` and `/exclude`.
4. Go to Actions → **Digest** → *Run workflow* (you can set `dry_run` first) to get a digest now. The first run downloads the embedding model (~90 MB), and later runs use the cache.
5. `/invite 5 14` creates a code for 5 people, valid 14 days.

## Done when
- [ ] `getWebhookInfo` shows your Worker URL and no errors
- [ ] Your profile arrived after uploading a CV
- [ ] A manual Digest run delivered jobs, and a second manual run delivered **different** jobs
- [ ] A friend joined with an invite code and received their own digest
