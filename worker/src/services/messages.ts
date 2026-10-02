import type { Profile } from "../domain";
import { esc, truncate } from "../util/text";

export const HELP = `<b>JobBot</b> sends you 10 CV-matched jobs at 07:00 and 17:00 (WAT).

<b>Get started</b>
• Send your CV as a <b>PDF</b>. I'll build your profile in about 2 minutes.

<b>Your profile</b>
/profile: show it
/titles Backend Engineer, Python Developer: set the job titles to search
/skills add Docker, AWS · /skills remove PHP · /skills set …
/exclude add unpaid, crypto · /exclude remove … · /exclude set …
/locations Nigeria, Worldwide, Africa, EMEA: places you can work from/in
/seniority mid, senior
/remote on|off: include remote jobs
/summary &lt;2-3 sentences about you&gt;

<b>Your digest</b>
/split 4 6: Nigerian vs international jobs per message
/saved: jobs you saved with 💾
/pause · /resume
/delete: delete all your data

Buttons under each job: 💾 save · ✖ not for me (fewer like it) · ✍ tailored CV bullets.`;

export const ADMIN_HELP = `<b>Admin</b>
/invite [uses] [days]: create an invite code (default 1 use, 14 days)
/users: list users
/approve &lt;chat_id&gt; · /block &lt;chat_id&gt;`;

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
    `<b>Skills:</b> ${list(p.skills)}\n` +
    `<b>Seniority:</b> ${list(p.seniority)}\n` +
    `<b>Remote OK:</b> ${p.remote_ok ? "yes" : "no"}\n` +
    `<b>Locations:</b> ${list(p.countries_ok)}\n` +
    `<b>Exclude:</b> ${list(p.exclude_keywords)}\n` +
    `<b>Summary:</b> ${p.summary ? esc(truncate(p.summary, 600)) : "<i>none</i>"}`
  );
}
