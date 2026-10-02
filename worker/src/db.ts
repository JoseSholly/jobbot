import { neon } from "@neondatabase/serverless";

/** Minimal SQL port. Repositories depend on this, not on a specific driver. */
export interface Sql {
  query<T = Record<string, unknown>>(text: string, params?: unknown[]): Promise<T[]>;
}

/** Neon's HTTP driver: one HTTPS round-trip per query, ideal for Workers. */
export function neonSql(databaseUrl: string): Sql {
  const sql = neon(databaseUrl);
  return {
    async query<T>(text: string, params: unknown[] = []): Promise<T[]> {
      return (await sql.query(text, params)) as T[];
    },
  };
}
