import type { Sql } from "../db";
import type { Sender, User, UserStatus } from "../domain";

interface Row {
  chat_id: string | number;
  username: string | null;
  first_name: string | null;
  status: UserStatus;
  is_admin: boolean;
  ng_quota: number;
  global_quota: number;
}

const toUser = (r: Row): User => ({
  chatId: Number(r.chat_id),
  username: r.username,
  firstName: r.first_name,
  status: r.status,
  isAdmin: r.is_admin,
  ngQuota: Number(r.ng_quota),
  globalQuota: Number(r.global_quota),
});

export class UserRepository {
  constructor(private readonly sql: Sql) {}

  async get(chatId: number): Promise<User | null> {
    const rows = await this.sql.query<Row>("SELECT * FROM users WHERE chat_id = $1", [chatId]);
    return rows[0] ? toUser(rows[0]) : null;
  }

  /** Insert if new (keeping existing status), refresh username/first name. */
  async upsert(s: Sender, status: UserStatus, isAdmin = false, ngQuota = 4, globalQuota = 6): Promise<User> {
    const rows = await this.sql.query<Row>(
      `INSERT INTO users (chat_id, username, first_name, status, is_admin, ng_quota, global_quota)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (chat_id) DO UPDATE SET
         username = EXCLUDED.username, first_name = EXCLUDED.first_name,
         is_admin = users.is_admin OR EXCLUDED.is_admin,
         status = CASE WHEN EXCLUDED.is_admin THEN 'active' ELSE users.status END,
         updated_at = now()
       RETURNING *`,
      [s.chatId, s.username, s.firstName, status, isAdmin, ngQuota, globalQuota],
    );
    return toUser(rows[0]!);
  }

  async setStatus(chatId: number, status: UserStatus, inviteCode?: string): Promise<User | null> {
    const rows = await this.sql.query<Row>(
      `UPDATE users SET status = $2, invite_code = COALESCE($3, invite_code), updated_at = now()
       WHERE chat_id = $1 RETURNING *`,
      [chatId, status, inviteCode ?? null],
    );
    return rows[0] ? toUser(rows[0]) : null;
  }

  async setQuotas(chatId: number, ng: number, global: number): Promise<void> {
    await this.sql.query(
      "UPDATE users SET ng_quota = $2, global_quota = $3, updated_at = now() WHERE chat_id = $1",
      [chatId, ng, global],
    );
  }

  async countActive(): Promise<number> {
    const rows = await this.sql.query<{ n: string }>(
      "SELECT count(*) AS n FROM users WHERE status = 'active'",
    );
    return Number(rows[0]?.n ?? 0);
  }

  async list(limit = 50): Promise<(User & { hasProfile: boolean })[]> {
    const rows = await this.sql.query<Row & { has_profile: boolean }>(
      `SELECT u.*, (p.data IS NOT NULL AND p.data <> '{}'::jsonb) AS has_profile
       FROM users u LEFT JOIN profiles p USING (chat_id)
       ORDER BY u.status, u.created_at LIMIT $1`,
      [limit],
    );
    return rows.map((r) => ({ ...toUser(r), hasProfile: Boolean(r.has_profile) }));
  }

  async delete(chatId: number): Promise<void> {
    await this.sql.query("DELETE FROM users WHERE chat_id = $1", [chatId]);
  }
}
