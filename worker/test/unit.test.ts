import { describe, expect, it } from "vitest";
import { parseCommand } from "../src/handlers/commands";
import { DEFAULT_PROFILE } from "../src/domain";
import { applyListEdit, parseEditArgs } from "../src/services/profileService";
import { tailorPrompt } from "../src/services/tailorService";
import { esc, inviteCode, parseList } from "../src/util/text";

describe("parseCommand", () => {
  it("parses commands with bot suffix and multi-line args", () => {
    expect(parseCommand("/start@JobBot ABCD2345")).toEqual({ command: "start", args: "ABCD2345" });
    expect(parseCommand("/summary line one\nline two")).toEqual({ command: "summary", args: "line one\nline two" });
    expect(parseCommand("/HELP")).toEqual({ command: "help", args: "" });
    expect(parseCommand("hello")).toBeNull();
  });
});

describe("list editing", () => {
  it("parses lists and verbs", () => {
    expect(parseList("Python, Django; python\n Docker ,")).toEqual(["Python", "Django", "Docker"]);
    expect(parseEditArgs("add AWS, GCP", "set")).toEqual({ op: "add", values: ["AWS", "GCP"] });
    expect(parseEditArgs("rm php", "add")).toEqual({ op: "remove", values: ["php"] });
    expect(parseEditArgs("Backend Engineer", "set")).toEqual({ op: "set", values: ["Backend Engineer"] });
  });

  it("applies add/remove/set case-insensitively with caps", () => {
    let p = { ...DEFAULT_PROFILE, skills: ["Python"] };
    p = applyListEdit(p, "skills", "add", ["python", "Go"]);
    expect(p.skills).toEqual(["Python", "Go"]);
    p = applyListEdit(p, "skills", "remove", ["PYTHON"]);
    expect(p.skills).toEqual(["Go"]);
    p = applyListEdit(p, "seniority", "set", ["Senior", "boss", "lead"]);
    expect(p.seniority).toEqual(["senior", "lead"]);
    const many = Array.from({ length: 20 }, (_, i) => `Title ${i}`);
    expect(applyListEdit(p, "target_titles", "set", many).target_titles).toHaveLength(8);
  });
});

describe("text utils", () => {
  it("escapes HTML and makes readable invite codes", () => {
    expect(esc("<a & b>")).toBe("&lt;a &amp; b&gt;");
    const code = inviteCode();
    expect(code).toMatch(/^[A-HJ-NP-Z2-9]{8}$/);
  });

  it("tailor prompt forbids invention and truncates", () => {
    const prompt = tailorPrompt("x".repeat(10000), { title: "Dev", company: "Acme", description: "y" });
    expect(prompt).toContain("never invent");
    expect(prompt.length).toBeLessThan(7000);
  });
});

describe("related titles and domains", () => {
  it("edits the new list fields and keeps old profiles working", () => {
    const old = { ...DEFAULT_PROFILE } as Partial<typeof DEFAULT_PROFILE>;
    delete old.related_titles;
    let p = applyListEdit({ ...DEFAULT_PROFILE, ...old }, "related_titles", "add", ["Virtual Assistant"]);
    p = applyListEdit(p, "related_titles", "add", ["virtual assistant", "Executive Assistant"]);
    expect(p.related_titles).toEqual(["Virtual Assistant", "Executive Assistant"]);
    expect(applyListEdit(p, "domains", "set", ["fintech", "e-commerce"]).domains).toEqual(["fintech", "e-commerce"]);
  });
});
