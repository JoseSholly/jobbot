"""Feedback-based re-ranking: nudge scores toward what the user saved, away from dismissals."""

from __future__ import annotations

import numpy as np

from jobbot.domain.models import ScoredJob


class FeedbackReranker:
    def __init__(self, max_adjust: float = 10.0, min_events: int = 1):
        self.max_adjust = max_adjust
        self.min_events = min_events

    def adjustment(
        self, job_vec: np.ndarray, saved: np.ndarray | None, dismissed: np.ndarray | None
    ) -> float:
        """Points in [-max_adjust, +max_adjust].

        Uses the max cosine similarity to any saved / dismissed job; only similarity above
        0.3 counts so unrelated history doesn't move scores.
        """

        def strength(matrix: np.ndarray | None) -> float:
            if matrix is None or len(matrix) == 0:
                return 0.0
            sims = matrix @ job_vec
            return float(max(0.0, (float(np.max(sims)) - 0.3) / 0.7))

        delta = strength(saved) - strength(dismissed)
        return float(np.clip(delta * self.max_adjust, -self.max_adjust, self.max_adjust))

    def apply(
        self,
        scored: list[ScoredJob],
        job_vectors: dict[str, np.ndarray],
        saved_vectors: list[np.ndarray],
        dismissed_vectors: list[np.ndarray],
        weights: dict[str, float],
    ) -> list[ScoredJob]:
        if len(saved_vectors) + len(dismissed_vectors) < self.min_events:
            return scored
        saved = np.vstack(saved_vectors) if saved_vectors else None
        dismissed = np.vstack(dismissed_vectors) if dismissed_vectors else None
        for item in scored:
            vec = job_vectors.get(item.job.id)
            if vec is None:
                continue
            item.breakdown.feedback = self.adjustment(vec, saved, dismissed)
            item.score = item.breakdown.total(weights)
        return scored
