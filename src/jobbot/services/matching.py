"""Per-user matching: hard filters -> score -> feedback re-rank -> quota selection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from jobbot.domain.models import Job, Profile, ScoredJob
from jobbot.services.filters import FilterContext, reject_reason
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


@dataclass(slots=True)
class Funnel:
    """Where a user's jobs were lost this run. Logged and stored in runs.stats."""

    total: int = 0
    rejected: Counter = field(default_factory=Counter)
    scored: int = 0
    above_min: int = 0
    top_scores: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "rejected": dict(self.rejected),
            "scored": self.scored,
            "above_min": self.above_min,
            "top_scores": self.top_scores,
        }


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
        funnel: Funnel | None = None,
    ) -> list[ScoredJob]:
        ctx = FilterContext(
            now=now,
            max_age_days=self.scorer.config.max_age_days,
            sent_ids=history.sent_ids,
            sent_keys=history.sent_keys,
            dismissed_ids=set(history.dismissed_ids),
        )
        candidates = []
        rejected: Counter = Counter()
        for job in jobs:
            reason = reject_reason(job, profile, ctx)
            if reason is None:
                candidates.append(job)
            else:
                rejected[reason] += 1
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
        ranked = sorted(scored, key=lambda s: s.score, reverse=True)
        if funnel is not None:
            funnel.total = len(jobs)
            funnel.rejected = rejected
            funnel.scored = len(ranked)
            funnel.above_min = sum(1 for s in ranked if s.score >= self.min_score)
            funnel.top_scores = [round(s.score, 1) for s in ranked[:5]]
        return ranked

    def pick(self, ranked: list[ScoredJob], ng_quota: int, global_quota: int) -> list[ScoredJob]:
        return select(ranked, ng_quota, global_quota, self.min_score)
