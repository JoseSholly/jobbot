import type { Reply } from "../domain";

/** Thin Telegram Bot API client (only the methods the bot uses). */
export class TelegramClient {
  constructor(private readonly token: string, private readonly fetchFn: typeof fetch = fetch) {}

  async call<T = unknown>(method: string, payload: Record<string, unknown>): Promise<T> {
    const doFetch = this.fetchFn;
    const res = await doFetch(`https://api.telegram.org/bot${this.token}/${method}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = (await res.json()) as { ok: boolean; result?: T; description?: string };
    if (!data.ok) throw new Error(`telegram ${method} failed: ${data.description ?? res.status}`);
    return data.result as T;
  }

  async send(reply: Reply): Promise<void> {
    await this.call("sendMessage", {
      chat_id: reply.chatId,
      text: reply.text,
      parse_mode: "HTML",
      link_preview_options: { is_disabled: true },
      ...(reply.buttons
        ? {
            reply_markup: {
              inline_keyboard: reply.buttons.map((row) =>
                row.map((b) => ({ text: b.text, callback_data: b.data })),
              ),
            },
          }
        : {}),
    });
  }

  async answerCallback(callbackQueryId: string, text?: string): Promise<void> {
    await this.call("answerCallbackQuery", { callback_query_id: callbackQueryId, text });
  }

  async typing(chatId: number): Promise<void> {
    await this.call("sendChatAction", { chat_id: chatId, action: "typing" }).catch(() => {});
  }
}
