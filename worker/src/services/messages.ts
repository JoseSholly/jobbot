import type { Profile } from "../domain";
import { esc, truncate } from "../util/text";

export const HELP = `<b>JobBot</b> delivers 10 CV-matched jobs at 07:00 and 17:00 WAT.

<b>Get started</b>
Send your CV as a <b>PDF</b>. I'll build your profile in about 2 minutes.

<b>Profile</b>
/profile — view your profile
/titles — set target job titles
   <code>/titles Backend Engineer, Python Developer</code>
/related — broader titles to also match
   <code>/related add Software Developer, Web Developer</code>
/skills — <code>add</code>, <code>remove</code>, or <code>set</code>
   <code>/skills add Docker, AWS</code>
/exclude — filter out keywords
   <code>/exclude add unpaid, crypto</code>
/locations — where you can work
   <code>/locations Nigeria, Worldwide, EMEA</code>
/seniority — <code>/seniority mid, senior</code>
/domains — industries, e.g. <code>/domains fintech, e-commerce</code>
/remote — <code>/remote on</code> or <code>/remote off</code>
/summary — a 2-3 sentence intro about you

<b>Digest</b>
/split — Nigerian vs international split
   <code>/split 4 6</code>
/saved — jobs you've saved
/pause — stop the digest
/resume — resume the digest
/delete — remove all your data

<b>Under each job</b>
💾 Save · ✖ Not for me · ✍ Tailor bullets`;

export const ADMIN_HELP = `<b>Admin</b>
/invite [uses] [days] — create an invite (default 1 use, 14 days)
/users — list users
/approve &lt;chat_id&gt; — approve a user
/block &lt;chat_id&gt; — block a user`;

export const PRIVACY = `<i>Privacy: your CV text and profile are stored in the bot's database to match jobs. ` +
  `If the operator enabled Gemini, CV text is sent to Google's Gemini API for parsing and tailoring. ` +
  `Use /delete at any time to remove everything.</i>`;

function list(values: string[]): string {
  return values.length ? esc(truncate(values.join(", "), 700)) : "<i>none</i>";
}

export function renderProfile(p: Profile, header = "Your profile"): string {
  return (
    `<b>${esc(header)}</b>\n\n` +
    `<b>Titles:</b> ${list(p.target_titles)}\n` +
    `<b>Also matching:</b> ${list(p.related_titles ?? [])}\n` +
    `<b>Skills:</b> ${list(p.skills)}\n` +
    `<b>Seniority:</b> ${list(p.seniority)}\n` +
    `<b>Remote OK:</b> ${p.remote_ok ? "yes" : "no"}\n` +
    `<b>Locations:</b> ${list(p.countries_ok)}\n` +
    `<b>Exclude:</b> ${list(p.exclude_keywords)}\n` +
    `<b>Industries:</b> ${list(p.domains ?? [])}\n` +
    `<b>Summary:</b> ${p.summary ? esc(truncate(p.summary, 600)) : "<i>none</i>"}`
  );
}
