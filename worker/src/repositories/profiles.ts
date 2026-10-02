import type { Sql } from "../db";
import { DEFAULT_PROFILE, type Profile } from "../domain";

interface Row {
  data: Partial<Profile> | null;
  cv_text: string | null;
  cv_file_id: string | null;
}

export interface StoredProfile {
  profile: Profile | null; // null until a CV has been parsed (or edits made)
  cvText: string | null;
  cvFileId: string | null;
}

export function withDefaults(data: Partial<Profile> | null | undefined): Profile {
  return { ...DEFAULT_PROFILE, ...(data ?? {}) };
}

export class ProfileRepository {
  constructor(private readonly sql: Sql) {}

  async get(chatId: number): Promise<StoredProfile> {
    const rows = await this.sql.query<Row>(
      "SELECT data, cv_text, cv_file_id FROM profiles WHERE chat_id = $1",
      [chatId],
    );
    const row = rows[0];
    const hasData = row?.data && Object.keys(row.data).length > 0;
    return {
      profile: hasData ? withDefaults(row!.data) : null,
      cvText: row?.cv_text ?? null,
      cvFileId: row?.cv_file_id ?? null,
    };
  }

  async setCvFile(chatId: number, fileId: string): Promise<void> {
    await this.sql.query(
      `INSERT INTO profiles (chat_id, cv_file_id) VALUES ($1, $2)
       ON CONFLICT (chat_id) DO UPDATE SET cv_file_id = EXCLUDED.cv_file_id, updated_at = now()`,
      [chatId, fileId],
    );
  }

  async save(chatId: number, profile: Profile): Promise<void> {
    await this.sql.query(
      `INSERT INTO profiles (chat_id, data) VALUES ($1, $2::jsonb)
       ON CONFLICT (chat_id) DO UPDATE SET data = EXCLUDED.data, updated_at = now()`,
      [chatId, JSON.stringify(profile)],
    );
  }
}
