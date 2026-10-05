"""Turn an uploaded CV into a matching profile, and keep it editable."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from jobbot.domain.models import Profile
from jobbot.domain.roles import related_titles_for
from jobbot.domain.synonyms import canonical
from jobbot.interfaces.ml import LLMClient
from jobbot.interfaces.notifier import FileDownloader, Notifier, OutgoingMessage
from jobbot.interfaces.repositories import ProfileRepository
from jobbot.services.cv_parser import heuristic_profile
from jobbot.services.formatting import render_profile

log = logging.getLogger(__name__)

MAX_CV_CHARS = 20_000
_MAX_TITLES = 4
_MAX_SKILLS = 12
_MAX_SUMMARY_CHARS = 300
_MAX_RELATED = 6
_MAX_DOMAINS = 4


def _dedup_ci(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def _tighten(p: Profile) -> Profile:
    summary = p.summary.strip()
    if len(summary) > _MAX_SUMMARY_CHARS:
        summary = summary[: _MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    titles = _dedup_ci(p.target_titles)[:_MAX_TITLES]
    taken = {t.lower() for t in titles}
    related = [t for t in _dedup_ci(p.related_titles) if t.lower() not in taken][:_MAX_RELATED]
    return replace(
        p,
        target_titles=titles,
        related_titles=related,
        domains=_dedup_ci(p.domains)[:_MAX_DOMAINS],
        skills=_dedup_ci([canonical(s) for s in p.skills])[:_MAX_SKILLS],
        seniority=_dedup_ci(p.seniority),
        exclude_keywords=_dedup_ci(p.exclude_keywords),
        summary=summary,
    )


class ProfileBuildError(Exception):
    """User-facing failure (bad PDF, empty text, ...)."""


class CVTextExtractor:
    """Small seam so tests don't need real PDFs."""

    def extract(self, data: bytes) -> str:  # pragma: no cover - replaced in tests
        from jobbot.adapters.pdf import pdf_to_text

        return pdf_to_text(data)


class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        llm: LLMClient | None = None,
        downloader: FileDownloader | None = None,
        notifier: Notifier | None = None,
        extractor: CVTextExtractor | None = None,
    ):
        self.profiles = profiles
        self.llm = llm
        self.downloader = downloader
        self.notifier = notifier
        self.extractor = extractor or CVTextExtractor()

    async def parse(self, cv_text: str) -> Profile:
        cv_text = cv_text.strip()[:MAX_CV_CHARS]
        if len(cv_text) < 100:
            raise ProfileBuildError(
                "I couldn't read text from that PDF. If it's a scanned image, please export "
                "a text-based PDF (e.g. from Word or Google Docs) and send it again."
            )
        fallback = heuristic_profile(cv_text)
        if self.llm is None:
            return fallback
        try:
            parsed = await self.llm.parse_cv(cv_text)
        except Exception:
            log.warning("LLM CV parsing failed; using heuristic parser", exc_info=True)
            parsed = None
        if parsed is None or not parsed.is_usable:
            return fallback
        parsed = _tighten(parsed)
        # Fill gaps the LLM left empty from the heuristic result (also tightened).
        titles = parsed.target_titles or fallback.target_titles
        skills = parsed.skills or fallback.skills
        return replace(
            parsed,
            skills=skills,
            target_titles=titles,
            related_titles=parsed.related_titles or related_titles_for(titles, skills),
            seniority=parsed.seniority or fallback.seniority,
            summary=parsed.summary or fallback.summary,
        )

    @staticmethod
    def merge_preferences(new: Profile, existing: Profile | None) -> Profile:
        """A new CV replaces CV-derived fields but keeps the user's location/exclusion prefs."""
        if existing is None:
            return new
        return replace(
            new,
            remote_ok=existing.remote_ok,
            countries_ok=existing.countries_ok or new.countries_ok,
            exclude_keywords=sorted({*existing.exclude_keywords, *new.exclude_keywords}, key=str.lower),
        )

    async def build_from_text(self, chat_id: int, cv_text: str) -> Profile:
        profile = self.merge_preferences(await self.parse(cv_text), self.profiles.get(chat_id))
        self.profiles.save(chat_id, profile, cv_text=cv_text[:MAX_CV_CHARS])
        return profile

    async def build_from_upload(self, chat_id: int) -> Profile:
        """Download the CV the user sent via Telegram, parse it, save it, and DM the result."""
        try:
            file_id = self.profiles.get_cv_file_id(chat_id)
            if not file_id:
                raise ProfileBuildError("I don't have a CV on file for you. Send me a PDF.")
            if self.downloader is None:
                raise RuntimeError("no file downloader configured")
            data = await self.downloader.download(file_id)
            try:
                text = self.extractor.extract(data)
            except Exception as exc:
                raise ProfileBuildError(
                    "That file doesn't look like a readable PDF. Please send your CV as a PDF."
                ) from exc
            profile = await self.build_from_text(chat_id, text)
        except ProfileBuildError as exc:
            await self._notify(chat_id, OutgoingMessage(text=f"⚠️ {exc}"))
            raise
        await self._notify(chat_id, render_profile(profile, header="✅ Profile ready"))
        await self._notify(
            chat_id,
            OutgoingMessage(
                text="You'll get your first digest at the next run (07:00 or 17:00 WAT). "
                "Review the profile above and fix anything that's off; good titles and skills "
                "make a big difference."
            ),
        )
        return profile

    async def rebuild_all(self, delay_seconds: float = 6.0) -> dict[int, str]:
        """Re-parse every stored CV with the current parser (no re-upload needed).

        Keeps each user's location/remote/exclusion preferences and DMs them the new profile.
        The delay keeps Gemini's free-tier per-minute limit happy.
        """
        results: dict[int, str] = {}
        for index, chat_id in enumerate(self.profiles.list_with_cv()):
            if index and delay_seconds:
                await asyncio.sleep(delay_seconds)
            cv_text = self.profiles.get_cv_text(chat_id) or ""
            try:
                profile = await self.build_from_text(chat_id, cv_text)
                await self._notify(chat_id, render_profile(profile, header="🔄 Profile updated"))
                results[chat_id] = "ok"
            except Exception as exc:  # one bad CV must not stop the rest
                log.warning("rebuild failed for %s: %s", chat_id, exc)
                results[chat_id] = f"failed: {exc}"[:200]
        return results

    async def _notify(self, chat_id: int, message: OutgoingMessage) -> None:
        if self.notifier:
            await self.notifier.send(chat_id, message)
