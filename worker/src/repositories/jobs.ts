import type { Sql } from "../db";
import type { Job } from "../domain";

export class JobRepository {
  constructor(private readonly sql: Sql) {}

  async get(jobId: string): Promise<Job | null> {
    const rows = await this.sql.query<Job>(
      "SELECT id, url, title, company, description, location FROM jobs WHERE id = $1",
      [jobId],
    );
    return rows[0] ?? null;
  }

  /** Only jobs that were actually sent to this user can be acted on by them. */
  async wasSentTo(chatId: number, jobId: string): Promise<boolean> {
    const rows = await this.sql.query(
      "SELECT 1 FROM sent WHERE chat_id = $1 AND job_id = $2",
      [chatId, jobId],
    );
    return rows.length > 0;
  }
}
