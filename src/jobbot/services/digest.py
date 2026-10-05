"""Orchestrates one digest run for every active user.

Fetch + embed jobs ONCE, then per user: filter -> score -> re-rank -> select ->
(optional) LLM reasons -> send -> remember what was sent.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from jobbot.domain.models import FeedbackAction, Job, Profile, ScoredJob, Slot, User, UserStatus
from jobbot.interfaces.ml import Embedder, LLMClient
from jobbot.interfaces.notifier import Notifier, OutgoingMessage, RecipientUnavailable
from jobbot.interfaces.repositories import (
    FeedbackRepository,
    JobRepository,
    ProfileRepository,
    RunRepository,
    SentRepository,
    UserRepository,
)
from jobbot.services.alerts import AlertService
from jobbot.services.formatting import render_digest, render_no_matches
from jobbot.services.ingestion import IngestionService, build_search_context
from jobbot.services.matching import Funnel, MatchingService, UserHistory
from jobbot.services.normalize import utcnow

log = logging.getLogger(__name__)


@dataclass(slots=True)
class DigestOptions:
    slot: Slot
    dry_run: bool = False
    only_chat_id: int | None = None
    max_keywords: int = 12
    max_skills: int = 4
    max_age_days: int = 14
    sent_retention_days: int = 60
    jobs_retention_days: int = 90
    match_reasons: bool = True
    max_reason_users: int = 50
    send_delay_seconds: float = 0.5
    notify_when_empty: bool = True
    # Skip if this slot was already delivered since this moment (start of today, local time).
    # Lets Cloudflare's cron and GitHub's cron both trigger a slot without double-sending.
    once_per_slot_since: datetime | None = None


@dataclass(slots=True)
class DigestReport:
    users_total: int = 0
    users_sent: int = 0
    users_failed: dict[int, str] = field(default_factory=dict)
    users_skipped: dict[int, str] = field(default_factory=dict)
    jobs_ingested: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    source_errors: dict[str, str] = field(default_factory=dict)
    previews: dict[int, list[OutgoingMessage]] = field(default_factory=dict)
    skipped_reason: str | None = None
    funnels: dict[int, dict] = field(default_factory=dict)

    def as_stats(self) -> dict[str, Any]:
        return {
            "users_total": self.users_total,
            "users_sent": self.users_sent,
            "users_failed": {str(k): v for k, v in self.users_failed.items()},
            "users_skipped": {str(k): v for k, v in self.users_skipped.items()},
            "jobs_ingested": self.jobs_ingested,
            "per_source": self.per_source,
            "source_errors": self.source_errors,
            "funnels": {str(k): v for k, v in self.funnels.items()},
        }


@dataclass(slots=True)
class DigestRepositories:
    users: UserRepository
    profiles: ProfileRepository
    jobs: JobRepository
    sent: SentRepository
    feedback: FeedbackRepository
    runs: RunRepository


class DigestService:
    def __init__(
        self,
        repos: DigestRepositories,
        ingestion: IngestionService,
        matching: MatchingService,
        notifier: Notifier,
        alerts: AlertService,
        embedder: Embedder | None = None,
        llm: LLMClient | None = None,
    ):
        self.repos = repos
        self.ingestion = ingestion
        self.matching = matching
        self.notifier = notifier
        self.alerts = alerts
        self.embedder = embedder
        self.llm = llm

    # ------------------------------------------------------------------ public
    async def run(self, opts: DigestOptions) -> DigestReport:
        report = DigestReport()
        since = opts.once_per_slot_since
        if since is not None and not opts.dry_run and self.repos.runs.delivered_since(opts.slot.value, since):
            report.skipped_reason = f"{opts.slot.value} digest already delivered today"
            log.info(report.skipped_reason)
            return report
        run_id = self.repos.runs.start(opts.slot.value)
        try:
            await self._run(opts, report)
        except Exception as exc:
            self.repos.runs.finish(run_id, "failed", report.as_stats(), traceback.format_exc())
            await self.alerts.alert(f"{opts.slot.value} digest crashed", f"{exc!r}")
            raise
        if opts.dry_run:
            status = "dry_run"  # never counts as delivered
        else:
            status = "ok" if not report.users_failed and not report.source_errors else "partial"
        self.repos.runs.finish(run_id, status, report.as_stats(), None)
        await self._maybe_alert(opts, report)
        return report

    # ----------------------------------------------------------------- private
    async def _run(self, opts: DigestOptions, report: DigestReport) -> None:
        now = utcnow()
        audience = self._load_audience(opts, report)
        report.users_total = len(audience)
        if not audience:
            log.info("no active users with a profile; nothing to do")
            return

        ctx = build_search_context([p for _, p in audience], opts.max_keywords, opts.max_skills)
        ingested = await self.ingestion.ingest(ctx)
        report.per_source, report.source_errors = ingested.per_source, ingested.errors
        if ingested.all_failed:
            # Don't tell users "no matches" when the real problem is that we fetched nothing.
            raise RuntimeError(
                "every job source failed: " + "; ".join(f"{k}: {v}" for k, v in ingested.errors.items())
            )

        cutoff = now - timedelta(days=opts.max_age_days)
        jobs = [j for j in ingested.jobs if j.posted_at is None or j.posted_at >= cutoff]
        report.jobs_ingested = len(jobs)
        job_vectors = self._embed_jobs(jobs)

        reasons_budget = opts.max_reason_users if opts.match_reasons else 0
        for user, profile in audience:
            try:
                funnel = Funnel()
                picked = self._match_user(user, profile, jobs, job_vectors, now, funnel)
                report.funnels[user.chat_id] = funnel.as_dict()
                log.info("user %s funnel: %s", user.chat_id, funnel.as_dict())
                if picked and self.llm and reasons_budget > 0:
                    reasons_budget -= 1
                    await self._add_reasons(profile, picked)
                await self._deliver(user, picked, job_vectors, opts, report)
            except RecipientUnavailable as exc:
                # The user blocked the bot or deleted their account: stop sending.
                log.info("user %s unreachable (%s); pausing", user.chat_id, exc)
                user.status = UserStatus.PAUSED
                self.repos.users.upsert(user)
                report.users_skipped[user.chat_id] = "unreachable; paused"
            except Exception as exc:
                log.exception("user %s failed", user.chat_id)
                report.users_failed[user.chat_id] = f"{type(exc).__name__}: {exc}"[:300]
            if not opts.dry_run and opts.send_delay_seconds:
                await asyncio.sleep(opts.send_delay_seconds)

        if not opts.dry_run:
            self.repos.sent.prune(opts.sent_retention_days)
            self.repos.jobs.prune(opts.jobs_retention_days)

    def _load_audience(self, opts: DigestOptions, report: DigestReport):
        if opts.only_chat_id is not None:
            user = self.repos.users.get(opts.only_chat_id)
            users = [user] if user else []
        else:
            users = self.repos.users.list_active()
        audience: list[tuple[User, Profile]] = []
        for user in users:
            profile = self.repos.profiles.get(user.chat_id)
            if profile is None or not profile.is_usable:
                report.users_skipped[user.chat_id] = "no profile yet"
                continue
            audience.append((user, profile))
        return audience

    def _embed(self, texts: list[str]) -> list[np.ndarray] | None:
        if not self.embedder or not texts:
            return None
        try:
            return [np.asarray(v, dtype=np.float32) for v in self.embedder.embed(texts)]
        except Exception:
            log.exception("embedding failed; falling back to lexical similarity")
            self.embedder = None
            return None

    def _embed_jobs(self, jobs: list[Job]) -> dict[str, np.ndarray]:
        vectors = self._embed([j.embedding_text for j in jobs])
        return {j.id: v for j, v in zip(jobs, vectors, strict=True)} if vectors else {}

    def _history(self, chat_id: int) -> UserHistory:
        sent_ids, sent_keys = self.repos.sent.sent_keys(chat_id)
        actions = self.repos.feedback.job_ids_by_action(chat_id)
        saved = actions.get(FeedbackAction.SAVE, [])
        dismissed = actions.get(FeedbackAction.DISMISS, [])
        stored = self.repos.jobs.get_embeddings(saved + dismissed)

        def vecs(ids: list[str]) -> list[np.ndarray]:
            return [np.asarray(stored[i], dtype=np.float32) for i in ids if i in stored]

        return UserHistory(sent_ids, sent_keys, saved, dismissed, vecs(saved), vecs(dismissed))

    def _match_user(self, user, profile, jobs, job_vectors, now, funnel=None) -> list[ScoredJob]:
        history = self._history(user.chat_id)
        profile_vecs = self._embed([profile.embedding_text]) if job_vectors else None
        profile_vec = profile_vecs[0] if profile_vecs else None
        ranked = self.matching.rank(jobs, profile, history, now, profile_vec, job_vectors, funnel)
        return self.matching.pick(ranked, user.ng_quota, user.global_quota)

    async def _add_reasons(self, profile: Profile, picked: list[ScoredJob]) -> None:
        try:
            reasons = await self.llm.match_reasons(profile, [s.job for s in picked])
        except Exception:
            log.warning("match reasons failed", exc_info=True)
            return
        if reasons and len(reasons) == len(picked):
            for item, reason in zip(picked, reasons, strict=True):
                item.reason = reason or None

    async def _deliver(self, user, picked, job_vectors, opts, report) -> None:
        if picked:
            messages = render_digest(opts.slot, picked)
        elif opts.notify_when_empty:
            messages = [render_no_matches(opts.slot)]
        else:
            messages = []
        if opts.dry_run:
            report.previews[user.chat_id] = messages
            report.users_sent += 1
            return
        for message in messages:
            await self.notifier.send(user.chat_id, message)
        if picked:
            jobs = [s.job for s in picked]
            embeddings = {j.id: job_vectors[j.id].tolist() for j in jobs if j.id in job_vectors}
            self.repos.jobs.upsert_many(jobs, embeddings)
            self.repos.sent.record(user.chat_id, [(s.job, s.score) for s in picked])
        report.users_sent += 1

    async def _maybe_alert(self, opts: DigestOptions, report: DigestReport) -> None:
        problems = []
        if report.per_source and not any(report.per_source.values()):
            problems.append("every source returned 0 jobs")
        if report.source_errors:
            problems.append(
                "sources failed: " + ", ".join(f"{k} ({v})" for k, v in report.source_errors.items())
            )
        if report.users_failed:
            problems.append(
                f"{len(report.users_failed)} user(s) failed: "
                + "; ".join(f"{k}: {v}" for k, v in list(report.users_failed.items())[:5])
            )
        if problems and not opts.dry_run:
            await self.alerts.alert(f"{opts.slot.value} digest had problems", "\n".join(problems))


def slot_for(now_local: datetime) -> Slot:
    return Slot.MORNING if now_local.hour < 12 else Slot.EVENING
