"""Render digests and profile summaries as Telegram HTML messages."""

from __future__ import annotations

import html

from jobbot.domain.models import Job, Profile, ScoredJob, Slot
from jobbot.domain.text import truncate
from jobbot.interfaces.notifier import Button, OutgoingMessage

TELEGRAM_LIMIT = 4096


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def location_line(job: Job) -> str:
    loc = job.location.strip()
    if job.remote:
        if not loc or loc.lower() == "remote":
            return "Remote"
        return loc if "remote" in loc.lower() else f"Remote - {loc}"
    return loc or "Location not stated"


def job_block(index: int, item: ScoredJob) -> str:
    job = item.job
    lines = [
        f"{index}. <b>{esc(truncate(job.title, 120))}</b>, {esc(truncate(job.company, 60))}",
        f"   {esc(truncate(location_line(job), 80))} | Match {round(item.score)}%",
    ]
    if item.reason:
        lines.append(f"   <i>{esc(truncate(item.reason, 200))}</i>")
    lines.append(f"   {esc(job.url)}")
    return "\n".join(lines)


def job_buttons(index: int, job_id: str) -> list[Button]:
    return [
        Button(f"💾 {index}", f"s:{job_id}"),
        Button(f"✖ {index}", f"d:{job_id}"),
        Button(f"✍ {index}", f"t:{job_id}"),
    ]


def render_digest(slot: Slot, items: list[ScoredJob]) -> list[OutgoingMessage]:
    """One message (or several if > 4096 chars) with Save / Dismiss / Tailor buttons per job."""
    title = "Morning" if slot is Slot.MORNING else "Evening"
    header = f"<b>{title} digest: {len(items)} job{'s' if len(items) != 1 else ''}</b>"
    footer = "\n\n<i>💾 save · ✖ not for me · ✍ tailored CV bullets</i>"

    messages: list[OutgoingMessage] = []
    text = header
    buttons: list[list[Button]] = []
    for i, item in enumerate(items, start=1):
        block = "\n\n" + job_block(i, item)
        if len(text) + len(block) + len(footer) > TELEGRAM_LIMIT and buttons:
            messages.append(OutgoingMessage(text=text, buttons=buttons))
            text, buttons = f"<b>{title} digest (cont.)</b>", []
        text += block
        buttons.append(job_buttons(i, item.job.id))
    messages.append(OutgoingMessage(text=text + footer, buttons=buttons or None))
    return messages


def render_no_matches(slot: Slot) -> OutgoingMessage:
    title = "Morning" if slot is Slot.MORNING else "Evening"
    return OutgoingMessage(
        text=f"<b>{title} digest</b>\n\nNo new jobs above your match threshold this time. "
        "Try broadening your profile with /titles or /skills."
    )


def render_profile(profile: Profile, header: str = "Your profile") -> OutgoingMessage:
    def fmt(values: list[str]) -> str:
        return esc(truncate(", ".join(values), 700)) if values else "<i>none</i>"

    text = (
        f"<b>{esc(header)}</b>\n\n"
        f"<b>Titles:</b> {fmt(profile.target_titles)}\n"
        f"<b>Skills:</b> {fmt(profile.skills)}\n"
        f"<b>Seniority:</b> {fmt(profile.seniority)}\n"
        f"<b>Remote OK:</b> {'yes' if profile.remote_ok else 'no'}\n"
        f"<b>Locations:</b> {fmt(profile.countries_ok)}\n"
        f"<b>Exclude:</b> {fmt(profile.exclude_keywords)}\n"
        f"<b>Summary:</b> {esc(truncate(profile.summary, 600)) or '<i>none</i>'}\n\n"
        "Edit with /titles, /skills, /exclude, /locations, /seniority, /summary. "
        "Send /help for examples."
    )
    return OutgoingMessage(text=text)
