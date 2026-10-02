import type { Services } from "../container";
import type { Reply, Sender } from "../domain";
import { ADMIN_HELP, HELP } from "../services/messages";

/** Parse "/cmd@BotName args" -> ["cmd", "args"]. */
export function parseCommand(text: string): { command: string; args: string } | null {
  const match = text.trim().match(/^\/([a-zA-Z_]+)(?:@\w+)?(?:\s+([\s\S]*))?$/);
  if (!match) return null;
  return { command: match[1]!.toLowerCase(), args: (match[2] ?? "").trim() };
}

type Handler = (s: Services, sender: Sender, args: string) => Promise<Reply[]>;

const PUBLIC: Record<string, Handler> = {
  start: (s, u, args) => s.users.start(u, args || undefined),
  join: (s, u, args) => s.users.join(u, args),
};

/** Commands that need an active (or paused) account. */
const MEMBER: Record<string, Handler> = {
  help: async (s, u) => [{ chatId: u.chatId, text: HELP + (s.users.isAdmin(u.chatId) ? `\n\n${ADMIN_HELP}` : "") }],
  profile: (s, u) => s.profiles.show(u.chatId),
  cv: async (_s, u) => [{ chatId: u.chatId, text: "Send your CV as a <b>PDF</b> file in this chat." }],
  titles: (s, u, a) => s.profiles.editList(u.chatId, "target_titles", a, "set"),
  skills: (s, u, a) => s.profiles.editList(u.chatId, "skills", a, "add"),
  exclude: (s, u, a) => s.profiles.editList(u.chatId, "exclude_keywords", a, "add"),
  locations: (s, u, a) => s.profiles.editList(u.chatId, "countries_ok", a, "set"),
  seniority: (s, u, a) => s.profiles.editList(u.chatId, "seniority", a, "set"),
  remote: (s, u, a) => s.profiles.setRemote(u.chatId, a),
  summary: (s, u, a) => s.profiles.setSummary(u.chatId, a),
  split: (s, u, a) => {
    const [ng, gl] = a.split(/\s+/).map(Number);
    return s.users.setSplit(u.chatId, ng ?? NaN, gl ?? NaN);
  },
  saved: (s, u) => s.feedback.listSaved(u.chatId),
  pause: (s, u) => s.users.pause(u.chatId),
  resume: (s, u) => s.users.resume(u.chatId),
  delete: async (s, u) => [s.users.deleteConfirmation(u.chatId)],
};

const ADMIN: Record<string, Handler> = {
  invite: (s, u, a) => {
    const [uses, days] = a.split(/\s+/).map(Number);
    return s.users.createInvite(u.chatId, uses || 1, days || 14);
  },
  users: (s, u) => s.users.listUsers(u.chatId),
  approve: (s, u, a) => s.users.approve(u.chatId, Number(a)),
  block: (s, u, a) => s.users.reject(u.chatId, Number(a)),
};

export async function handleCommand(s: Services, sender: Sender, text: string): Promise<Reply[]> {
  const parsed = parseCommand(text);
  if (!parsed) return [];
  const { command, args } = parsed;

  const pub = PUBLIC[command];
  if (pub) return pub(s, sender, args);

  if (ADMIN[command]) {
    return s.users.isAdmin(sender.chatId) ? ADMIN[command]!(s, sender, args) : [];
  }

  const user = await s.users.get(sender.chatId);
  if (!user || (user.status !== "active" && user.status !== "paused")) {
    if (user?.status === "blocked") return [];
    return [{ chatId: sender.chatId, text: "You don't have access yet. Send /start or <code>/join CODE</code>." }];
  }
  const handler = MEMBER[command];
  if (!handler) return [{ chatId: sender.chatId, text: "Unknown command. Send /help." }];
  return handler(s, sender, args);
}
