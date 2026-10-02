import type { GeminiClient } from "../clients/gemini";
import type { Reply } from "../domain";
import type { JobRepository } from "../repositories/jobs";
import type { ProfileRepository } from "../repositories/profiles";
import { esc, truncate } from "../util/text";

export function tailorPrompt(cv: string, job: { title: string; company: string; description: string }): string {
  return `You are a careful CV coach. Using ONLY facts from the candidate's CV/profile below, write
4-5 tailored CV bullet points for this job application. Rules: start each bullet with a strong
verb, mirror the job's key terms where truthful, quantify only with numbers present in the CV,
never invent employers, titles, tools or metrics. Then add one line starting "Gap:" naming the
most important requirement the CV doesn't show (or "Gap: none obvious").
Output plain text, bullets prefixed with "• ". No preamble.

CANDIDATE:
${truncate(cv, 6000)}

JOB: ${job.title} at ${job.company}
${truncate(job.description, 3500)}`;
}

/** ✍ button: tailored CV bullets for one job, generated with Gemini. */
export class TailorService {
  constructor(
    private readonly profiles: ProfileRepository,
    private readonly jobs: JobRepository,
    private readonly llm: GeminiClient | null,
  ) {}

  get enabled(): boolean {
    return this.llm !== null;
  }

  async tailor(chatId: number, jobId: string): Promise<Reply[]> {
    if (!this.llm) return [{ chatId, text: "Tailored bullets aren't enabled on this bot." }];
    if (!(await this.jobs.wasSentTo(chatId, jobId))) {
      return [{ chatId, text: "That job is no longer available." }];
    }
    const [job, stored] = await Promise.all([this.jobs.get(jobId), this.profiles.get(chatId)]);
    if (!job) return [{ chatId, text: "That job is no longer available." }];
    const p = stored.profile;
    const candidate = [
      stored.cvText ?? "",
      p ? `Summary: ${p.summary}\nSkills: ${p.skills.join(", ")}\nTitles: ${p.target_titles.join(", ")}` : "",
    ].join("\n\n").trim();
    if (!candidate) return [{ chatId, text: "I need your CV first. Send it as a PDF." }];

    const bullets = await this.llm.generate(tailorPrompt(candidate, job));
    return [{
      chatId,
      text: `✍ <b>Tailored for ${esc(truncate(job.title, 100))}, ${esc(truncate(job.company, 60))}</b>\n\n` +
        `${esc(truncate(bullets, 3300))}\n\n${esc(job.url)}\n\n<i>Double-check every bullet before using it.</i>`,
    }];
  }
}
