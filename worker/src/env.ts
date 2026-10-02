/** Bindings available to the Worker (vars from wrangler.toml + secrets). */
export interface Env {
  TELEGRAM_BOT_TOKEN: string;
  WEBHOOK_SECRET: string;
  DATABASE_URL: string;
  ADMIN_CHAT_ID: string;
  GITHUB_TOKEN?: string;
  GITHUB_REPO?: string;
  GITHUB_REF?: string;
  GEMINI_API_KEY?: string;
  GEMINI_MODEL?: string;
  MAX_USERS?: string;
  DEFAULT_NG_QUOTA?: string;
  DEFAULT_GLOBAL_QUOTA?: string;
}
