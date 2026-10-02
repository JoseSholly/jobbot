import type { Reply, Sender, User } from "../domain";
import type { InviteRepository } from "../repositories/invites";
import type { ProfileRepository } from "../repositories/profiles";
import type { UserRepository } from "../repositories/users";
import { esc, inviteCode } from "../util/text";
import { ADMIN_HELP, HELP, PRIVACY } from "./messages";

export interface UserServiceConfig {
  adminChatId: number;
  maxUsers: number;
  defaultNgQuota: number;
  defaultGlobalQuota: number;
}

/** Onboarding, access control and account lifecycle. */
export class UserService {
  constructor(
    private readonly users: UserRepository,
    private readonly invites: InviteRepository,
    private readonly profiles: ProfileRepository,
    private readonly cfg: UserServiceConfig,
  ) {}

  isAdmin(chatId: number): boolean {
    return chatId === this.cfg.adminChatId;
  }

  async get(chatId: number): Promise<User | null> {
    return this.users.get(chatId);
  }

  /** /start [invite-code] (also handles t.me/<bot>?start=<code> deep links). */
  async start(sender: Sender, code?: string): Promise<Reply[]> {
    const admin = this.isAdmin(sender.chatId);
    const existing = await this.users.get(sender.chatId);
    if (existing?.status === "blocked") return [];

    const user = await this.users.upsert(
      sender,
      admin ? "active" : "pending",
      admin,
      this.cfg.defaultNgQuota,
      this.cfg.defaultGlobalQuota,
    );
    if (user.status === "active" || user.status === "paused") {
      return [{ chatId: sender.chatId, text: await this.welcomeBack(user) }];
    }
    if (code) return this.join(sender, code);

    const isNew = !existing;
    const replies: Reply[] = [
      {
        chatId: sender.chatId,
        text:
          `👋 Hi${sender.firstName ? " " + esc(sender.firstName) : ""}! JobBot is invite-only.\n\n` +
          `If you have an invite code, send <code>/join CODE</code>. ` +
          `Otherwise I've asked the admin to approve you; you'll get a message here.`,
      },
    ];
    if (isNew) replies.push(this.approvalRequest(sender));
    return replies;
  }

  async join(sender: Sender, code: string): Promise<Reply[]> {
    const user = await this.users.get(sender.chatId);
    if (!user) return this.start(sender, code);
    if (user.status === "blocked") return [];
    if (user.status === "active") {
      return [{ chatId: sender.chatId, text: "You're already in ✅. Send your CV as a PDF to update your profile." }];
    }
    if (!(await this.hasCapacity())) {
      return [{ chatId: sender.chatId, text: "Sorry, JobBot is full right now. Please try again later." }];
    }
    if (!code.trim() || !(await this.invites.redeem(code))) {
      return [{ chatId: sender.chatId, text: "❌ That invite code is invalid, used up or expired." }];
    }
    await this.users.setStatus(sender.chatId, "active", code.trim().toUpperCase());
    return [
      { chatId: sender.chatId, text: this.activatedText() },
      { chatId: this.cfg.adminChatId, text: `➕ ${this.label(sender)} joined with invite <code>${esc(code.trim().toUpperCase())}</code>.` },
    ];
  }

  async approve(adminId: number, chatId: number): Promise<Reply[]> {
    if (!this.isAdmin(adminId)) return [];
    if (!(await this.hasCapacity())) {
      return [{ chatId: adminId, text: `Can't approve: MAX_USERS (${this.cfg.maxUsers}) reached.` }];
    }
    const user = await this.users.setStatus(chatId, "active");
    if (!user) return [{ chatId: adminId, text: `Unknown user ${chatId}.` }];
    return [
      { chatId: adminId, text: `✅ Approved ${this.label(user)}.` },
      { chatId, text: this.activatedText() },
    ];
  }

  async reject(adminId: number, chatId: number): Promise<Reply[]> {
    if (!this.isAdmin(adminId)) return [];
    const user = await this.users.setStatus(chatId, "blocked");
    if (!user) return [{ chatId: adminId, text: `Unknown user ${chatId}.` }];
    return [{ chatId: adminId, text: `⛔ Blocked ${this.label(user)}.` }];
  }

  async pause(chatId: number): Promise<Reply[]> {
    const user = await this.users.get(chatId);
    if (!user || user.status !== "active") return [{ chatId, text: "Nothing to pause." }];
    await this.users.setStatus(chatId, "paused");
    return [{ chatId, text: "⏸ Paused. Send /resume to get digests again." }];
  }

  async resume(chatId: number): Promise<Reply[]> {
    const user = await this.users.get(chatId);
    if (!user || user.status !== "paused") return [{ chatId, text: "You're not paused." }];
    await this.users.setStatus(chatId, "active");
    return [{ chatId, text: "▶️ Resumed. Your next digest arrives at 07:00 or 17:00 WAT." }];
  }

  async setSplit(chatId: number, ng: number, global: number): Promise<Reply[]> {
    const valid = (n: number) => Number.isInteger(n) && n >= 0 && n <= 10;
    if (!valid(ng) || !valid(global) || ng + global === 0 || ng + global > 10) {
      return [{ chatId, text: "Usage: <code>/split 4 6</code> (Nigeria, international). Each 0-10, total 1-10." }];
    }
    await this.users.setQuotas(chatId, ng, global);
    return [{ chatId, text: `✅ Each digest will have up to ${ng} Nigerian and ${global} international jobs.` }];
  }

  deleteConfirmation(chatId: number): Reply {
    return {
      chatId,
      text: "⚠️ Delete your account, CV, profile and history? This can't be undone.",
      buttons: [[{ text: "Yes, delete everything", data: "del:yes" }, { text: "Cancel", data: "del:no" }]],
    };
  }

  async deleteAccount(chatId: number): Promise<Reply[]> {
    await this.users.delete(chatId); // cascades to profiles, sent, feedback
    return [{ chatId, text: "🗑 Done. All your data has been deleted. Send /start if you ever want to come back." }];
  }

  async createInvite(adminId: number, uses = 1, days = 14): Promise<Reply[]> {
    if (!this.isAdmin(adminId)) return [];
    const safeUses = Math.min(Math.max(1, uses || 1), 100);
    const safeDays = Math.min(Math.max(1, days || 14), 365);
    const code = inviteCode();
    await this.invites.create(code, adminId, safeUses, safeDays);
    return [{
      chatId: adminId,
      text: `🎟 Invite <code>${code}</code> (${safeUses} use${safeUses > 1 ? "s" : ""}, ${safeDays} days).\n` +
        `Share: <code>/join ${code}</code>`,
    }];
  }

  async listUsers(adminId: number): Promise<Reply[]> {
    if (!this.isAdmin(adminId)) return [];
    const users = await this.users.list(100);
    if (!users.length) return [{ chatId: adminId, text: "No users yet." }];
    const lines = users.map((u) =>
      `<code>${u.chatId}</code> ${u.status}${u.isAdmin ? " (admin)" : ""} ${this.label(u)}${u.hasProfile ? "" : " · no profile"}`,
    );
    return [{ chatId: adminId, text: `<b>Users (${users.length})</b>\n` + lines.join("\n") }];
  }

  // ---------------------------------------------------------------- helpers
  private async hasCapacity(): Promise<boolean> {
    return (await this.users.countActive()) < this.cfg.maxUsers;
  }

  private label(u: { chatId: number; username: string | null; firstName: string | null }): string {
    if (u.username) return "@" + esc(u.username);
    return esc(u.firstName ?? String(u.chatId));
  }

  private approvalRequest(sender: Sender): Reply {
    return {
      chatId: this.cfg.adminChatId,
      text: `🆕 Access request from ${this.label(sender)} (<code>${sender.chatId}</code>).`,
      buttons: [[
        { text: "✅ Approve", data: `a:${sender.chatId}` },
        { text: "⛔ Reject", data: `r:${sender.chatId}` },
      ]],
    };
  }

  private activatedText(): string {
    return `🎉 You're in!\n\nNow send me your <b>CV as a PDF</b>. I'll turn it into a matching profile ` +
      `(about 2 minutes), then you'll get 10 jobs at 07:00 and 17:00 WAT.\n\n${PRIVACY}`;
  }

  private async welcomeBack(user: User): Promise<string> {
    const { profile, cvFileId } = await this.profiles.get(user.chatId);
    const status = user.status === "paused" ? "\n\n⏸ Your digest is paused. Send /resume." : "";
    const next = profile
      ? "Your profile is set up. /profile to review it."
      : cvFileId
        ? "I'm still building your profile from your CV…"
        : "Send me your <b>CV as a PDF</b> to get started.";
    return `Welcome back 👋 ${next}${status}\n\n${HELP}` + (user.isAdmin ? `\n\n${ADMIN_HELP}` : "");
  }
}
