import type { GitHubClient } from "../clients/github";
import type { Reply } from "../domain";

export type Slot = "morning" | "evening";

/** 06:00 UTC cron = 07:00 WAT morning digest; 16:00 UTC = 17:00 WAT evening digest. */
export function slotForCron(scheduledTime: number): Slot {
  return new Date(scheduledTime).getUTCHours() < 11 ? "morning" : "evening";
}

/**
 * Starts the digest on time. GitHub's own cron is often hours late or skipped, so the
 * Worker's Cron Trigger dispatches digest.yml instead. The Python side ignores the run
 * if that slot was already delivered today (--once-per-slot), so duplicates are harmless.
 */
export class ScheduleService {
  constructor(
    private readonly github: GitHubClient | null,
    private readonly adminChatId: number,
    private readonly attempts = 3,
    private readonly sleep: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms)),
  ) {}

  /** Returns messages for the admin if dispatch failed (empty on success). */
  async triggerDigest(slot: Slot): Promise<Reply[]> {
    if (!this.github) {
      return [{
        chatId: this.adminChatId,
        text: "⚠️ Can't start the digest on time: GITHUB_TOKEN is not set on the Worker. " +
          "GitHub's backup schedule will still run, possibly late.",
      }];
    }
    let lastError = "";
    for (let attempt = 1; attempt <= this.attempts; attempt++) {
      try {
        await this.github.dispatch("digest.yml", { slot, trigger: "cloudflare" });
        return [];
      } catch (err) {
        lastError = String(err).slice(0, 300);
        if (attempt < this.attempts) await this.sleep(2000 * attempt);
      }
    }
    return [{
      chatId: this.adminChatId,
      text: `⚠️ Couldn't start the ${slot} digest: ${lastError}\n` +
        "GitHub's backup schedule may still run it. You can also run it from Actions → Digest.",
    }];
  }
}
