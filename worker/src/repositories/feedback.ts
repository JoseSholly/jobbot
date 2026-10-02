import type { Sql } from "../db";
import type { FeedbackAction, Job } from "../domain";

export class FeedbackRepository {
  constructor(private readonly sql: Sql) {}

  async record(chatId: number, jobId: string, action: FeedbackAction): Promise<void> {
    await this.sql.query(
      `INSERT INTO feedback (chat_id, job_id, action) VALUES ($1, $2, $3)
       ON CONFLICT (chat_id, job_id) DO UPDATE SET action = EXCLUDED.action, created_at = now()`,
      [chatId, jobId, action],
    );
  }

  async saved(chatId: number, limit = 20): Promise<Job[]> {
    return this.sql.query<Job>(
      `SELECT j.id, j.url, j.title, j.company, j.description, j.location
       FROM feedback f JOIN jobs j ON j.id = f.job_id
       WHERE f.chat_id = $1 AND f.action = 'save'
       ORDER BY f.created_at DESC LIMIT $2`,
      [chatId, limit],
    );
  }
}
