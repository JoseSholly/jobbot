import { describe, expect, it } from "vitest";
import { GeminiClient } from "../src/clients/gemini";
import { GitHubClient } from "../src/clients/github";
import { TelegramClient } from "../src/clients/telegram";

/**
 * Cloudflare's fetch throws "Illegal invocation" when called as a method of another
 * object (e.g. `this.fetchFn(...)`). Node doesn't, so emulate the check here.
 */
function strictFetch(response: () => Response) {
  return function (this: unknown, _input: RequestInfo | URL, _init?: RequestInit) {
    if (this !== undefined && this !== globalThis) throw new TypeError("Illegal invocation");
    return Promise.resolve(response());
  } as typeof fetch;
}

describe("clients call fetch without a bound receiver", () => {
  it("telegram", async () => {
    const tg = new TelegramClient("T", strictFetch(() => Response.json({ ok: true, result: 1 })));
    await expect(tg.call("getMe", {})).resolves.toBe(1);
  });

  it("github", async () => {
    const gh = new GitHubClient("T", "o/r", "main", strictFetch(() => new Response(null, { status: 204 })));
    await expect(gh.dispatch("build_profile.yml", { chat_id: "1" })).resolves.toBeUndefined();
  });

  it("gemini", async () => {
    const body = { candidates: [{ content: { parts: [{ text: "• bullet" }] } }] };
    const gemini = new GeminiClient("K", "m", strictFetch(() => Response.json(body)));
    await expect(gemini.generate("hi")).resolves.toBe("• bullet");
  });
});
