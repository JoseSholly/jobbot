"""Composition root: the ONLY place that knows which concrete adapter backs which interface.

Entrypoints ask the container for ready-to-use services; tests build services directly
with in-memory fakes instead.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import httpx

from jobbot.adapters.db.pool import Database
from jobbot.adapters.db.repositories import (
    PgFeedbackRepository,
    PgInviteRepository,
    PgJobRepository,
    PgProfileRepository,
    PgRunRepository,
    PgSentRepository,
    PgUserRepository,
)
from jobbot.adapters.embedder import FastEmbedEmbedder
from jobbot.adapters.gemini import GeminiClient
from jobbot.adapters.http import make_client
from jobbot.adapters.memory import (
    MemoryFeedbackRepository,
    MemoryInviteRepository,
    MemoryJobRepository,
    MemoryProfileRepository,
    MemoryRunRepository,
    MemorySentRepository,
    MemoryUserRepository,
)
from jobbot.adapters.sources.registry import build_sources
from jobbot.adapters.telegram import (
    ConsoleNotifier,
    TelegramClient,
    TelegramFileDownloader,
    TelegramNotifier,
)
from jobbot.config import Settings
from jobbot.domain.models import Profile, User, UserStatus
from jobbot.interfaces.notifier import Notifier
from jobbot.services.alerts import AlertService
from jobbot.services.digest import DigestRepositories, DigestService
from jobbot.services.ingestion import IngestionService
from jobbot.services.matching import MatchingService
from jobbot.services.profile import ProfileService
from jobbot.services.rerank import FeedbackReranker
from jobbot.services.scoring import Scorer, ScoringConfig
from jobbot.services.users import UserService

log = logging.getLogger(__name__)

LOCAL_CHAT_ID = 0


@dataclass
class Container:
    settings: Settings
    dry_run: bool = False
    local_profile: Profile | None = None  # run without a database for one local profile
    only_sources: set[str] | None = None
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack)
    _http: httpx.AsyncClient | None = None
    _db: Database | None = None
    _repos: DigestRepositories | None = None
    _invites: object | None = None

    async def __aenter__(self) -> Container:
        http = self.settings.http
        self._http = await self._stack.enter_async_context(
            make_client(
                timeout=float(http.get("timeout_seconds", 30)),
                user_agent=http.get("user_agent", "JobBot/0.1"),
            )
        )
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()
        if self._db is not None:
            self._db.close()

    # ------------------------------------------------------------- adapters
    @property
    def http(self) -> httpx.AsyncClient:
        assert self._http is not None, "use `async with Container(...)`"
        return self._http

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.settings.secrets.database_url)
        return self._db

    def repositories(self) -> DigestRepositories:
        if self._repos is not None:
            return self._repos
        if self.local_profile is not None:
            chat_id = self.local_chat_id
            users = MemoryUserRepository(
                [
                    User(
                        chat_id=chat_id,
                        username="local",
                        status=UserStatus.ACTIVE,
                        ng_quota=int(self.settings.digest.get("default_ng_quota", 4)),
                        global_quota=int(self.settings.digest.get("default_global_quota", 6)),
                    )
                ]
            )
            self._repos = DigestRepositories(
                users=users,
                profiles=MemoryProfileRepository({chat_id: self.local_profile}),
                jobs=MemoryJobRepository(),
                sent=MemorySentRepository(),
                feedback=MemoryFeedbackRepository(),
                runs=MemoryRunRepository(),
            )
            self._invites = MemoryInviteRepository()
        else:
            db = self.db
            self._repos = DigestRepositories(
                users=PgUserRepository(db),
                profiles=PgProfileRepository(db),
                jobs=PgJobRepository(db),
                sent=PgSentRepository(db),
                feedback=PgFeedbackRepository(db),
                runs=PgRunRepository(db),
            )
            self._invites = PgInviteRepository(db)
        return self._repos

    @property
    def local_chat_id(self) -> int:
        return self.settings.secrets.admin_chat_id or LOCAL_CHAT_ID

    def telegram(self) -> TelegramClient:
        return TelegramClient(self.settings.secrets.telegram_bot_token, self.http)

    def notifier(self) -> Notifier:
        if self.dry_run or not self.settings.secrets.telegram_bot_token:
            return ConsoleNotifier()
        return TelegramNotifier(self.telegram())

    def llm(self) -> GeminiClient | None:
        key = self.settings.secrets.gemini_api_key
        if not key:
            return None
        return GeminiClient(key, self.http, model=self.settings.llm.get("model", "gemini-2.5-flash"))

    def embedder(self) -> FastEmbedEmbedder:
        return FastEmbedEmbedder(
            self.settings.raw.get("embedding", {}).get("model", "sentence-transformers/all-MiniLM-L6-v2")
        )

    # ------------------------------------------------------------- services
    def alert_service(self) -> AlertService:
        return AlertService(self.notifier(), self.settings.secrets.admin_chat_id)

    def digest_service(self) -> DigestService:
        digest, scoring = self.settings.digest, self.settings.scoring
        max_age = int(digest.get("max_age_days", 14))
        matching = MatchingService(
            scorer=Scorer(ScoringConfig.from_settings(scoring, max_age)),
            reranker=FeedbackReranker(
                max_adjust=float(scoring.get("feedback_max_adjust", 10)),
                min_events=int(scoring.get("feedback_min_events", 1)),
            ),
            min_score=float(digest.get("min_score", 50)),
        )
        return DigestService(
            repos=self.repositories(),
            ingestion=IngestionService(build_sources(self.settings, self.http, self.only_sources)),
            matching=matching,
            notifier=self.notifier(),
            alerts=self.alert_service(),
            embedder=self.embedder(),
            llm=self.llm() if self.settings.llm.get("match_reasons", True) else None,
        )

    def profile_service(self) -> ProfileService:
        token = self.settings.secrets.telegram_bot_token
        return ProfileService(
            profiles=self.repositories().profiles,
            llm=self.llm(),
            downloader=TelegramFileDownloader(self.telegram()) if token else None,
            notifier=self.notifier(),
        )

    def user_service(self) -> UserService:
        repos = self.repositories()
        return UserService(
            repos.users,
            self._invites,  # type: ignore[arg-type]
            default_ng_quota=int(self.settings.digest.get("default_ng_quota", 4)),
            default_global_quota=int(self.settings.digest.get("default_global_quota", 6)),
        )
