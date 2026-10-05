/**
 * Runs the real services + repositories against Postgres, with Telegram/GitHub/Gemini faked.
 *   TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/jobbot_test npm test
 */
import { readFileSync } from "node:fs";
import pg from "pg";
import { afterAll, beforeEach, describe, expect, it } from "vitest";
import type { Services } from "../src/container";
import type { Sql } from "../src/db";
import type { Reply } from "../src/domain";
import { routeUpdate } from "../src/handlers/router";
import type { TgUpdate } from "../src/handlers/types";
import { FeedbackRepository } from "../src/repositories/feedback";
import { InviteRepository } from "../src/repositories/invites";
import { JobRepository } from "../src/repositories/jobs";
import { ProfileRepository } from "../src/repositories/profiles";
import { UserRepository } from "../src/repositories/users";
import { CvService } from "../src/services/cvService";
import { FeedbackService } from "../src/services/feedbackService";
import { ProfileService } from "../src/services/profileService";
import { TailorService } from "../src/services/tailorService";
import { UserService } from "../src/services/userService";

const DSN = process.env.TEST_DATABASE_URL;
const ADMIN = 1;
const ALICE = 1001;

const pool = DSN ? new pg.Pool({ connectionString: DSN }) : null;
const sql: Sql = {
  async query<T>(text: string, params: unknown[] = []) {
    return (await pool!.query(text, params)).rows as T[];
  },
};

class FakeTelegram {
  sent: Reply[] = [];
  toasts: (string | undefined)[] = [];
  async send(r: Reply) { this.sent.push(r); }
  async answerCallback(_id: string, text?: string) { this.toasts.push(text); }
  async typing() {}
  textsFor(chatId: number) { return this.sent.filter((r) => r.chatId === chatId).map((r) => r.text); }
}

function build(opts: { github?: boolean; gemini?: boolean; maxUsers?: number } = {}) {
  const telegram = new FakeTelegram();
  const dispatched: Record<string, string>[] = [];
  const github = opts.github === false ? null : ({
    dispatch: async (_wf: string, inputs: Record<string, string>) => { dispatched.push(inputs); },
  } as never);
  const gemini = opts.gemini === false ? null : ({ generate: async () => "• Built Django APIs\nGap: none obvious" } as never);
  const users = new UserRepository(sql);
  const profiles = new ProfileRepository(sql);
  const jobs = new JobRepository(sql);
  const services = {
    telegram: telegram as never,
    users: new UserService(users, new InviteRepository(sql), profiles, {
      adminChatId: ADMIN, maxUsers: opts.maxUsers ?? 50, defaultNgQuota: 4, defaultGlobalQuota: 6,
    }),
    profiles: new ProfileService(profiles),
    cv: new CvService(users, profiles, github, ADMIN),
    feedback: new FeedbackService(new FeedbackRepository(sql), jobs),
    tailor: new TailorService(profiles, jobs, gemini),
  } satisfies Services;
  const pending: Promise<unknown>[] = [];
  const run = async (update: Partial<TgUpdate>) => {
    await routeUpdate(services, { update_id: 1, ...update }, { later: (t) => pending.push(t) });
    await Promise.all(pending.splice(0));
  };
  return { telegram, dispatched, run };
}

const msg = (chatId: number, text: string, extra: object = {}): Partial<TgUpdate> => ({
  message: { message_id: 1, chat: { id: chatId, type: "private" }, from: { id: chatId, username: `u${chatId}`, first_name: "Test" }, text, ...extra },
});
const tap = (chatId: number, data: string): Partial<TgUpdate> => ({
  callback_query: { id: "cb", from: { id: chatId }, data },
});

describe.skipIf(!DSN)("worker against Postgres", () => {
  beforeEach(async () => {
    await pool!.query("DROP SCHEMA public CASCADE; CREATE SCHEMA public;");
    await pool!.query(readFileSync(new URL("../../migrations/001_init.sql", import.meta.url), "utf8"));
  });
  afterAll(async () => { await pool?.end(); });

  it("admin is auto-activated; stranger is pending and admin gets approve buttons", async () => {
    const { telegram, run } = build();
    await run(msg(ADMIN, "/start"));
    expect(telegram.textsFor(ADMIN)[0]).toContain("Welcome back");

    await run(msg(ALICE, "/start"));
    expect(telegram.textsFor(ALICE)[0]).toContain("invite-only");
    const request = telegram.sent.find((r) => r.chatId === ADMIN && r.buttons);
    expect(request?.buttons?.[0]?.[0]?.data).toBe(`a:${ALICE}`);

    await run(msg(ALICE, "/profile"));
    expect(telegram.textsFor(ALICE).at(-1)).toContain("don't have access");

    await run(tap(ALICE, `a:${ALICE}`)); // non-admin can't approve
    await run(tap(ADMIN, `a:${ALICE}`));
    expect(telegram.textsFor(ALICE).at(-1)).toContain("You're in");
  });

  it("invite codes: valid once, then used up; bare code works", async () => {
    const { telegram, run } = build();
    await run(msg(ADMIN, "/invite 1 7"));
    const code = /<code>([A-Z2-9]{8})<\/code>/.exec(telegram.textsFor(ADMIN).at(-1)!)![1]!;
    await run(msg(ALICE, code));
    expect(telegram.textsFor(ALICE).at(-1)).toContain("You're in");
    await run(msg(2002, `/start ${code}`));
    expect(telegram.textsFor(2002).at(-1)).toContain("invalid, used up or expired");
  });

  it("respects MAX_USERS", async () => {
    const { telegram, run } = build({ maxUsers: 1 });
    await run(msg(ADMIN, "/start")); // admin takes the only slot
    await run(msg(ADMIN, "/invite 5"));
    const code = /<code>([A-Z2-9]{8})<\/code>/.exec(telegram.textsFor(ADMIN).at(-1)!)![1]!;
    await run(msg(ALICE, `/join ${code}`));
    expect(telegram.textsFor(ALICE).at(-1)).toContain("full");
  });

  it("CV upload dispatches the build workflow; non-PDF rejected", async () => {
    const { telegram, dispatched, run } = build();
    await run(msg(ADMIN, "/start"));
    await run(msg(ADMIN, "", { text: undefined, document: { file_id: "F1", file_name: "cv.docx", mime_type: "application/msword" } }));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("PDF");
    await run(msg(ADMIN, "", { text: undefined, document: { file_id: "F2", file_name: "cv.pdf", mime_type: "application/pdf", file_size: 1000 } }));
    expect(dispatched).toEqual([{ chat_id: String(ADMIN) }]);
    const row = await pool!.query("SELECT cv_file_id FROM profiles WHERE chat_id = $1", [ADMIN]);
    expect(row.rows[0].cv_file_id).toBe("F2");
  });

  it("CV upload without GitHub token notifies admin", async () => {
    const { telegram, run } = build({ github: false });
    await run(msg(ADMIN, "/start"));
    await run(msg(ADMIN, "", { text: undefined, document: { file_id: "F", file_name: "a.pdf" } }));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("jobbot-build-profile --chat-id");
  });

  it("profile edits persist as JSON the Python side can read", async () => {
    const { telegram, run } = build();
    await run(msg(ADMIN, "/start"));
    await run(msg(ADMIN, "/titles Backend Engineer, Python Developer"));
    await run(msg(ADMIN, "/skills add Python, Django"));
    await run(msg(ADMIN, "/skills remove django"));
    await run(msg(ADMIN, "/exclude add unpaid"));
    await run(msg(ADMIN, "/related Software Developer, Web Developer"));
    await run(msg(ADMIN, "/domains fintech, e-commerce"));
    await run(msg(ADMIN, "/remote off"));
    await run(msg(ADMIN, "/split 2 8"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("2 Nigerian and 8 international");
    const { rows } = await pool!.query("SELECT data FROM profiles WHERE chat_id = $1", [ADMIN]);
    expect(rows[0].data).toMatchObject({
      target_titles: ["Backend Engineer", "Python Developer"], skills: ["Python"],
      exclude_keywords: ["unpaid"], remote_ok: false,
      related_titles: ["Software Developer", "Web Developer"], domains: ["fintech", "e-commerce"],
    });
    const quotas = await pool!.query("SELECT ng_quota, global_quota FROM users WHERE chat_id = $1", [ADMIN]);
    expect(quotas.rows[0]).toEqual({ ng_quota: 2, global_quota: 8 });
    await run(msg(ADMIN, "/split 9 9"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("Usage");
  });

  it("save / dismiss / tailor buttons on a sent job", async () => {
    const { telegram, run } = build();
    await run(msg(ADMIN, "/start"));
    await pool!.query(`INSERT INTO jobs (id, source, url, title, company, region) VALUES ('j1','x','https://e.com/1','Python Dev','Acme','GLOBAL')`);
    await pool!.query(`INSERT INTO sent (chat_id, job_id, dedupe_key) VALUES ($1, 'j1', 'acme|python dev')`, [ADMIN]);
    await run(tap(ADMIN, "s:j1"));
    expect(telegram.toasts.at(-1)).toContain("Saved");
    await run(msg(ADMIN, "/saved"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("Python Dev");
    await run(tap(ADMIN, "d:j1"));
    const fb = await pool!.query("SELECT action FROM feedback WHERE chat_id = $1", [ADMIN]);
    expect(fb.rows).toEqual([{ action: "dismiss" }]);
    await run(tap(ADMIN, "t:unknown"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("no longer available");
    await pool!.query(`INSERT INTO profiles (chat_id, data, cv_text) VALUES ($1, '{"skills":["Django"]}', 'cv text')`, [ADMIN]);
    await run(tap(ADMIN, "t:j1"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("Built Django APIs");
  });

  it("pause, resume and delete", async () => {
    const { telegram, run } = build();
    await run(msg(ADMIN, "/start"));
    await run(msg(ADMIN, "/pause"));
    await run(msg(ADMIN, "/resume"));
    expect(telegram.textsFor(ADMIN).at(-1)).toContain("Resumed");
    await run(msg(ADMIN, "/delete"));
    await run(tap(ADMIN, "del:yes"));
    const { rows } = await pool!.query("SELECT count(*)::int AS n FROM users");
    expect(rows[0].n).toBe(0);
  });
});
