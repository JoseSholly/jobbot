"""Turn an uploaded CV into a matching profile, and keep it editable."""

from __future__ import annotations

import logging
from dataclasses import replace

from jobbot.domain.models import Profile
from jobbot.interfaces.ml import LLMClient
from jobbot.interfaces.notifier import FileDownloader, Notifier, OutgoingMessage
from jobbot.interfaces.repositories import ProfileRepository
from jobbot.services.cv_parser import heuristic_profile
from jobbot.services.formatting import render_profile

log = logging.getLogger(__name__)

MAX_CV_CHARS = 20_000


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
        # Fill gaps the LLM left empty from the heuristic result.
        return replace(
            parsed,
            skills=parsed.skills or fallback.skills,
            target_titles=parsed.target_titles or fallback.target_titles,
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

    async def _notify(self, chat_id: int, message: OutgoingMessage) -> None:
        if self.notifier:
            await self.notifier.send(chat_id, message)
