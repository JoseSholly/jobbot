import type { Profile, Reply } from "../domain";
import type { ProfileRepository } from "../repositories/profiles";
import { withDefaults } from "../repositories/profiles";
import { parseList } from "../util/text";
import { renderProfile } from "./messages";

export type ListField = "target_titles" | "skills" | "exclude_keywords" | "countries_ok" | "seniority";
export type ListOp = "add" | "remove" | "set";

const SENIORITY = ["intern", "junior", "mid", "senior", "lead"];
const MAX_ITEMS: Record<ListField, number> = {
  target_titles: 8,
  skills: 40,
  exclude_keywords: 40,
  countries_ok: 15,
  seniority: 5,
};

/** Pure: apply one list edit. Exported for unit tests. */
export function applyListEdit(profile: Profile, field: ListField, op: ListOp, values: string[]): Profile {
  const current = profile[field];
  const lower = (s: string) => s.toLowerCase();
  let next: string[];
  if (op === "set") {
    next = values;
  } else if (op === "add") {
    const have = new Set(current.map(lower));
    next = [...current, ...values.filter((v) => !have.has(lower(v)))];
  } else {
    const drop = new Set(values.map(lower));
    next = current.filter((v) => !drop.has(lower(v)));
  }
  if (field === "seniority") next = next.map(lower).filter((v) => SENIORITY.includes(v));
  return { ...profile, [field]: next.slice(0, MAX_ITEMS[field]) };
}

/** Parse "add a, b" / "remove a" / "set a, b" / "a, b" (defaults to defaultOp). */
export function parseEditArgs(args: string, defaultOp: ListOp): { op: ListOp; values: string[] } {
  const match = args.trim().match(/^(add|remove|rm|del|set)\b\s*(.*)$/is);
  if (!match) return { op: defaultOp, values: parseList(args) };
  const verb = match[1]!.toLowerCase();
  const op: ListOp = verb === "add" ? "add" : verb === "set" ? "set" : "remove";
  return { op, values: parseList(match[2] ?? "") };
}

/** Viewing and hand-editing a user's matching profile. */
export class ProfileService {
  constructor(private readonly profiles: ProfileRepository) {}

  async show(chatId: number): Promise<Reply[]> {
    const { profile, cvFileId } = await this.profiles.get(chatId);
    if (!profile) {
      return [{
        chatId,
        text: cvFileId
          ? "⏳ Your profile is still being built from your CV. Try again in a minute."
          : "You don't have a profile yet. Send me your <b>CV as a PDF</b>.",
      }];
    }
    return [{ chatId, text: renderProfile(profile) }];
  }

  async editList(chatId: number, field: ListField, args: string, defaultOp: ListOp): Promise<Reply[]> {
    const { op, values } = parseEditArgs(args, defaultOp);
    if (!values.length && op !== "set") {
      return [{ chatId, text: usage(field) }];
    }
    const { profile } = await this.profiles.get(chatId);
    const updated = applyListEdit(withDefaults(profile), field, op, values);
    await this.profiles.save(chatId, updated);
    return [{ chatId, text: renderProfile(updated, "✅ Profile updated") }];
  }

  async setRemote(chatId: number, arg: string): Promise<Reply[]> {
    const value = arg.trim().toLowerCase();
    if (!["on", "off", "yes", "no"].includes(value)) {
      return [{ chatId, text: "Usage: <code>/remote on</code> or <code>/remote off</code>" }];
    }
    const { profile } = await this.profiles.get(chatId);
    const updated = { ...withDefaults(profile), remote_ok: value === "on" || value === "yes" };
    await this.profiles.save(chatId, updated);
    return [{ chatId, text: `✅ Remote jobs ${updated.remote_ok ? "included" : "excluded"}.` }];
  }

  async setSummary(chatId: number, text: string): Promise<Reply[]> {
    const summary = text.trim().slice(0, 1500);
    if (summary.length < 20) {
      return [{ chatId, text: "Usage: <code>/summary</code> followed by 2-3 sentences about your experience." }];
    }
    const { profile } = await this.profiles.get(chatId);
    await this.profiles.save(chatId, { ...withDefaults(profile), summary });
    return [{ chatId, text: "✅ Summary updated. It's used for semantic matching." }];
  }
}

function usage(field: ListField): string {
  const cmd = {
    target_titles: "titles",
    skills: "skills",
    exclude_keywords: "exclude",
    countries_ok: "locations",
    seniority: "seniority",
  }[field];
  return `Usage: <code>/${cmd} add a, b</code> · <code>/${cmd} remove a</code> · <code>/${cmd} set a, b</code>`;
}
