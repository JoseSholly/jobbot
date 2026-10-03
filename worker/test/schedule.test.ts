import { describe, expect, it } from "vitest";
import { ScheduleService, slotForCron } from "../src/services/scheduleService";

const noSleep = async () => {};

describe("ScheduleService", () => {
  it("maps cron times to slots", () => {
    expect(slotForCron(Date.UTC(2026, 9, 3, 6, 0))).toBe("morning");
    expect(slotForCron(Date.UTC(2026, 9, 3, 16, 0))).toBe("evening");
  });

  it("dispatches digest.yml with the slot and cloudflare trigger", async () => {
    const calls: [string, Record<string, string>][] = [];
    const github = { dispatch: async (wf: string, inputs: Record<string, string>) => { calls.push([wf, inputs]); } };
    const replies = await new ScheduleService(github as never, 1, 3, noSleep).triggerDigest("morning");
    expect(replies).toEqual([]);
    expect(calls).toEqual([["digest.yml", { slot: "morning", trigger: "cloudflare" }]]);
  });

  it("retries, then alerts the admin", async () => {
    let n = 0;
    const flaky = { dispatch: async () => { n++; if (n < 3) throw new Error("502"); } };
    expect(await new ScheduleService(flaky as never, 1, 3, noSleep).triggerDigest("evening")).toEqual([]);
    expect(n).toBe(3);

    const down = { dispatch: async () => { throw new Error("github dispatch 401: Bad credentials"); } };
    const [alert] = await new ScheduleService(down as never, 1, 3, noSleep).triggerDigest("evening");
    expect(alert?.chatId).toBe(1);
    expect(alert?.text).toContain("Bad credentials");
  });

  it("alerts when no GitHub token is configured", async () => {
    const [alert] = await new ScheduleService(null, 1).triggerDigest("morning");
    expect(alert?.text).toContain("GITHUB_TOKEN");
  });
});
