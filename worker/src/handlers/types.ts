/** The subset of Telegram's Update object the bot handles. */
export interface TgUser {
  id: number;
  username?: string;
  first_name?: string;
}

export interface TgMessage {
  message_id: number;
  chat: { id: number; type: string };
  from?: TgUser;
  text?: string;
  document?: { file_id: string; file_name?: string; mime_type?: string; file_size?: number };
}

export interface TgCallbackQuery {
  id: string;
  from: TgUser;
  message?: { chat: { id: number } };
  data?: string;
}

export interface TgUpdate {
  update_id: number;
  message?: TgMessage;
  callback_query?: TgCallbackQuery;
}
