import type { Reply } from "../domain";
import type { GitHubClient } from "../clients/github";
import type { ProfileRepository } from "../repositories/profiles";
import type { UserRepository } from "../repositories/users";

export interface IncomingDocument {
  fileId: string;
  fileName?: string;
  mimeType?: string;
  fileSize?: number;
}

const MAX_BYTES = 10 * 1024 * 1024; // Telegram lets bots download up to 20 MB; CVs are small.

/** Accepts CV uploads and kicks off the profile build on GitHub Actions. */
export class CvService {
  constructor(
    private readonly users: UserRepository,
    private readonly profiles: ProfileRepository,
    private readonly github: GitHubClient | null,
    private readonly adminChatId: number,
  ) {}

  async receive(chatId: number, doc: IncomingDocument): Promise<Reply[]> {
    const user = await this.users.get(chatId);
    if (!user || (user.status !== "active" && user.status !== "paused")) {
      return [{ chatId, text: "You need access first. Send /start." }];
    }
    const isPdf = doc.mimeType === "application/pdf" || /\.pdf$/i.test(doc.fileName ?? "");
    if (!isPdf) return [{ chatId, text: "Please send your CV as a <b>PDF</b> file." }];
    if ((doc.fileSize ?? 0) > MAX_BYTES) {
      return [{ chatId, text: "That file is over 10 MB. Please send a smaller PDF." }];
    }

    await this.profiles.setCvFile(chatId, doc.fileId);
    if (!this.github) {
      return [
        { chatId, text: "📄 Got your CV. The admin will build your profile shortly." },
        { chatId: this.adminChatId, text: `📄 New CV from <code>${chatId}</code>. Run: <code>uv run jobbot-build-profile --chat-id ${chatId}</code>` },
      ];
    }
    try {
      await this.github.dispatch("build_profile.yml", { chat_id: String(chatId) });
    } catch (err) {
      return [
        { chatId, text: "📄 Got your CV, but I couldn't start processing. The admin has been notified." },
        { chatId: this.adminChatId, text: `⚠️ build_profile dispatch failed for <code>${chatId}</code>: ${String(err).slice(0, 300)}` },
      ];
    }
    return [{ chatId, text: "📄 Got your CV! Building your profile; I'll message you in about 2 minutes." }];
  }
}
