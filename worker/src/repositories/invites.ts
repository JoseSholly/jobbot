import type { Sql } from "../db";

export class InviteRepository {
  constructor(private readonly sql: Sql) {}

  async create(code: string, createdBy: number, maxUses: number, daysValid: number): Promise<void> {
    await this.sql.query(
      `INSERT INTO invites (code, created_by, max_uses, expires_at)
       VALUES ($1, $2, $3, now() + make_interval(days => $4))`,
      [code, createdBy, maxUses, daysValid],
    );
  }

  /** Atomically consume one use. Returns false if unknown, used up or expired. */
  async redeem(code: string): Promise<boolean> {
    const rows = await this.sql.query(
      `UPDATE invites SET uses = uses + 1
       WHERE code = $1 AND uses < max_uses AND (expires_at IS NULL OR expires_at > now())
       RETURNING code`,
      [code.trim().toUpperCase()],
    );
    return rows.length > 0;
  }
}
