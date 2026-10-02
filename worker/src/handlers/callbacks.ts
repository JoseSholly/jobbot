import type { Services } from "../container";
import type { Reply } from "../domain";
import type { TgCallbackQuery } from "./types";

export interface CallbackResult {
  toast?: string;
  replies: Reply[];
  /** Slow work (LLM) that should run after answering the button tap. */
  background?: () => Promise<Reply[]>;
}

/** Button taps. callback_data is "<action>:<id>" (Telegram caps it at 64 bytes). */
export async function handleCallback(s: Services, q: TgCallbackQuery): Promise<CallbackResult> {
  const chatId = q.from.id;
  const [action, id = ""] = (q.data ?? "").split(":", 2);

  switch (action) {
    case "a":
      return { toast: "Approved", replies: await s.users.approve(chatId, Number(id)) };
    case "r":
      return { toast: "Rejected", replies: await s.users.reject(chatId, Number(id)) };
    case "del":
      if (id === "yes") return { toast: "Deleted", replies: await s.users.deleteAccount(chatId) };
      return { toast: "Cancelled", replies: [] };
  }

  const user = await s.users.get(chatId);
  if (!user || (user.status !== "active" && user.status !== "paused")) {
    return { toast: "You don't have access.", replies: [] };
  }
  switch (action) {
    case "s":
      return { toast: await s.feedback.record(chatId, id, "save"), replies: [] };
    case "d":
      return { toast: await s.feedback.record(chatId, id, "dismiss"), replies: [] };
    case "t":
      if (!s.tailor.enabled) return { toast: "Tailoring isn't enabled.", replies: [] };
      return {
        toast: "✍ Writing tailored bullets…",
        replies: [],
        background: () => s.tailor.tailor(chatId, id),
      };
    default:
      return { toast: "Unknown action", replies: [] };
  }
}
