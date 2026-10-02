import type { Services } from "../container";
import type { Reply, Sender } from "../domain";
import { handleCallback } from "./callbacks";
import { handleCommand } from "./commands";
import type { TgUpdate } from "./types";

const INVITE_RE = /^[A-Z2-9]{8}$/;

export interface Scheduler {
  /** Run work after the webhook response (Cloudflare ctx.waitUntil). */
  later(task: Promise<unknown>): void;
}

/** Entry point for one Telegram update. Sends replies via Telegram; never throws. */
export async function routeUpdate(s: Services, update: TgUpdate, scheduler: Scheduler): Promise<void> {
  const send = async (replies: Reply[]) => {
    for (const reply of replies) {
      try {
        await s.telegram.send(reply);
      } catch (err) {
        console.error("send failed", reply.chatId, err);
      }
    }
  };

  if (update.callback_query) {
    const q = update.callback_query;
    const result = await handleCallback(s, q);
    await s.telegram.answerCallback(q.id, result.toast).catch(() => {});
    await send(result.replies);
    if (result.background) {
      const task = result.background;
      scheduler.later((async () => {
        await s.telegram.typing(q.from.id);
        try {
          await send(await task());
        } catch (err) {
          console.error("background task failed", err);
          await send([{ chatId: q.from.id, text: "Sorry, that didn't work. Please try again later." }]);
        }
      })());
    }
    return;
  }

  const msg = update.message;
  if (!msg || msg.chat.type !== "private" || !msg.from) return; // private chats only
  const sender: Sender = {
    chatId: msg.chat.id,
    username: msg.from.username ?? null,
    firstName: msg.from.first_name ?? null,
  };

  if (msg.document) {
    const d = msg.document;
    await send(await s.cv.receive(sender.chatId, {
      fileId: d.file_id, fileName: d.file_name, mimeType: d.mime_type, fileSize: d.file_size,
    }));
    return;
  }
  const text = msg.text?.trim() ?? "";
  if (text.startsWith("/")) {
    await send(await handleCommand(s, sender, text));
    return;
  }
  // A bare invite code also works.
  if (INVITE_RE.test(text.toUpperCase())) {
    await send(await s.users.join(sender, text));
    return;
  }
  await send([{ chatId: sender.chatId, text: "Send /help to see what I can do, or send your CV as a PDF." }]);
}
