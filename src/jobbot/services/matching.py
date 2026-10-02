"""Per-user matching: hard filters -> score -> feedback re-rank -> quota selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from jobbot.domain.models import Job, Profile, ScoredJob
from jobbot.services.filters import FilterContext, apply_filters
from jobbot.services.rerank import FeedbackReranker
from jobbot.services.scoring import Scorer
from jobbot.services.selection import select


@dataclass(slots=True)
class UserHistory:
    sent_ids: set[str]
    sent_keys: set[str]
    saved_ids: list[str]
    dismissed_ids: list[str]
    saved_vectors: list[np.ndarray]
    dismissed_vectors: list[np.ndarray]


class MatchingService:
    def __init__(self, scorer: Scorer, reranker: FeedbackReranker, min_score: float):
        self.scorer = scorer
        self.reranker = reranker
        self.min_score = min_score

    def rank(
        self,
        jobs: list[Job],
        profile: Profile,
        history: UserHistory,
        now: datetime,
        profile_vec: np.ndarray | None,
        job_vectors: dict[str, np.ndarray],
    ) -> list[ScoredJob]:
        ctx = FilterContext(
            now=now,
            max_age_days=self.scorer.config.max_age_days,
            sent_ids=history.sent_ids,
            sent_keys=history.sent_keys,
            dismissed_ids=set(history.dismissed_ids),
        )
        candidates = apply_filters(jobs, profile, ctx)
        scored = [
            self.scorer.score(job, profile, now, profile_vec, job_vectors.get(job.id)) for job in candidates
        ]
        scored = self.reranker.apply(
            scored,
            job_vectors,
            history.saved_vectors,
            history.dismissed_vectors,
            self.scorer.config.weights,
        )
        return sorted(scored, key=lambda s: s.score, reverse=True)

    def pick(self, ranked: list[ScoredJob], ng_quota: int, global_quota: int) -> list[ScoredJob]:
        return select(ranked, ng_quota, global_quota, self.min_score)
