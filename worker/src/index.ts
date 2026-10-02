import { buildServices } from "./container";
import type { Env } from "./env";
import { routeUpdate } from "./handlers/router";
import type { TgUpdate } from "./handlers/types";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return new Response("JobBot worker is running.");
    }
    if (request.method !== "POST" || url.pathname !== "/telegram") {
      return new Response("Not found", { status: 404 });
    }
    // Telegram echoes the secret we passed to setWebhook; reject anything else.
    if (request.headers.get("x-telegram-bot-api-secret-token") !== env.WEBHOOK_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update: TgUpdate;
    try {
      update = (await request.json()) as TgUpdate;
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    const services = buildServices(env);
    const scheduler = { later: (task: Promise<unknown>) => ctx.waitUntil(task) };
    // Answer Telegram immediately; do the work in the background so slow DB/LLM calls
    // never cause Telegram to retry the update.
    ctx.waitUntil(
      routeUpdate(services, update, scheduler).catch((err) => console.error("update failed", err)),
    );
    return new Response("ok");
  },
} satisfies ExportedHandler<Env>;
