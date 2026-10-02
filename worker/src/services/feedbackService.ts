import type { FeedbackAction, Reply } from "../domain";
import type { FeedbackRepository } from "../repositories/feedback";
import type { JobRepository } from "../repositories/jobs";
import { esc, truncate } from "../util/text";

/** Save / Dismiss buttons. Feeds the Python re-ranker on the next digest. */
export class FeedbackService {
  constructor(private readonly feedback: FeedbackRepository, private readonly jobs: JobRepository) {}

  /** Returns the toast text shown on the button tap. */
  async record(chatId: number, jobId: string, action: FeedbackAction): Promise<string> {
    if (!(await this.jobs.wasSentTo(chatId, jobId))) return "That job is no longer available.";
    await this.feedback.record(chatId, jobId, action);
    return action === "save" ? "💾 Saved. See /saved" : "✖ Noted. You'll see fewer jobs like this.";
  }

  async listSaved(chatId: number): Promise<Reply[]> {
    const jobs = await this.feedback.saved(chatId, 20);
    if (!jobs.length) return [{ chatId, text: "No saved jobs yet. Tap 💾 under a job in your digest." }];
    const lines = jobs.map((j, i) =>
      `${i + 1}. <b>${esc(truncate(j.title, 100))}</b>, ${esc(truncate(j.company, 60))}\n   ${esc(j.url)}`,
    );
    return [{ chatId, text: `<b>Saved jobs</b>\n\n${lines.join("\n\n")}` }];
  }
}
