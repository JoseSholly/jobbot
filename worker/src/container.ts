import { GeminiClient } from "./clients/gemini";
import { GitHubClient } from "./clients/github";
import { TelegramClient } from "./clients/telegram";
import { neonSql, type Sql } from "./db";
import type { Env } from "./env";
import { FeedbackRepository } from "./repositories/feedback";
import { InviteRepository } from "./repositories/invites";
import { JobRepository } from "./repositories/jobs";
import { ProfileRepository } from "./repositories/profiles";
import { UserRepository } from "./repositories/users";
import { CvService } from "./services/cvService";
import { FeedbackService } from "./services/feedbackService";
import { ProfileService } from "./services/profileService";
import { TailorService } from "./services/tailorService";
import { UserService } from "./services/userService";

export interface Services {
  telegram: TelegramClient;
  users: UserService;
  profiles: ProfileService;
  cv: CvService;
  feedback: FeedbackService;
  tailor: TailorService;
}

/** Composition root: the only place that wires concrete clients/repos into services. */
export function buildServices(env: Env, sql: Sql = neonSql(env.DATABASE_URL)): Services {
  const adminChatId = Number(env.ADMIN_CHAT_ID);
  const userRepo = new UserRepository(sql);
  const profileRepo = new ProfileRepository(sql);
  const jobRepo = new JobRepository(sql);
  const github = env.GITHUB_TOKEN && env.GITHUB_REPO
    ? new GitHubClient(env.GITHUB_TOKEN, env.GITHUB_REPO, env.GITHUB_REF || "main")
    : null;
  const gemini = env.GEMINI_API_KEY
    ? new GeminiClient(env.GEMINI_API_KEY, env.GEMINI_MODEL || "gemini-2.5-flash")
    : null;

  return {
    telegram: new TelegramClient(env.TELEGRAM_BOT_TOKEN),
    users: new UserService(userRepo, new InviteRepository(sql), profileRepo, {
      adminChatId,
      maxUsers: Number(env.MAX_USERS || 50),
      defaultNgQuota: Number(env.DEFAULT_NG_QUOTA || 4),
      defaultGlobalQuota: Number(env.DEFAULT_GLOBAL_QUOTA || 6),
    }),
    profiles: new ProfileService(profileRepo),
    cv: new CvService(userRepo, profileRepo, github, adminChatId),
    feedback: new FeedbackService(new FeedbackRepository(sql), jobRepo),
    tailor: new TailorService(profileRepo, jobRepo, gemini),
  };
}
