"""Score a job against a profile (0-100). Pure functions + a small Scorer class."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

import numpy as np

from jobbot.domain.models import Job, Profile, ScoreBreakdown, ScoredJob
from jobbot.domain.text import contains_term, normalize_key, tokens

DEFAULT_WEIGHTS = {"semantic": 0.60, "skills": 0.25, "title": 0.10, "recency": 0.05}


@dataclass(slots=True)
class ScoringConfig:
    weights: dict[str, float]
    semantic_floor: float = 0.15
    semantic_ceiling: float = 0.65
    skill_saturation: int = 5
    max_age_days: int = 14

    @classmethod
    def from_settings(cls, scoring: dict, max_age_days: int) -> ScoringConfig:
        return cls(
            weights={**DEFAULT_WEIGHTS, **(scoring.get("weights") or {})},
            semantic_floor=float(scoring.get("semantic_floor", 0.15)),
            semantic_ceiling=float(scoring.get("semantic_ceiling", 0.65)),
            skill_saturation=int(scoring.get("skill_saturation", 5)),
            max_age_days=max_age_days,
        )


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def scale(value: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return 0.0
    return max(0.0, min(1.0, (value - floor) / (ceiling - floor)))


def skill_score(job: Job, skills: list[str], saturation: int) -> float:
    if not skills:
        return 0.0
    haystack = f"{job.title} {job.description}".lower()
    matched = sum(1 for s in skills if contains_term(haystack, s))
    return min(1.0, matched / max(1, min(saturation, len(skills))))


def title_score(job_title: str, target_titles: list[str]) -> float:
    if not target_titles:
        return 0.0
    jt = normalize_key(job_title)
    jt_tokens = tokens(jt)
    best = 0.0
    for target in target_titles:
        tt = normalize_key(target)
        tt_tokens = tokens(tt)
        if not tt_tokens:
            continue
        if tt in jt:
            return 1.0
        overlap = len(jt_tokens & tt_tokens) / len(tt_tokens)
        ratio = SequenceMatcher(None, jt, tt).ratio()
        best = max(best, 0.7 * overlap + 0.3 * ratio)
    return min(1.0, best)


def recency_score(posted_at: datetime | None, now: datetime, max_age_days: int) -> float:
    if posted_at is None:
        return 0.3  # unknown date: small, not zero
    age_days = max(0.0, (now - posted_at).total_seconds() / 86400)
    return max(0.0, 1.0 - age_days / max(1, max_age_days))


def lexical_similarity(a: str, b: str) -> float:
    """Fallback for when no embedding model is available: Jaccard-ish overlap."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / (len(ta) ** 0.5 * len(tb) ** 0.5)


class Scorer:
    def __init__(self, config: ScoringConfig):
        self.config = config

    def score(
        self,
        job: Job,
        profile: Profile,
        now: datetime,
        profile_vec: np.ndarray | None,
        job_vec: np.ndarray | None,
    ) -> ScoredJob:
        cfg = self.config
        if profile_vec is not None and job_vec is not None:
            raw_sem = cosine(profile_vec, job_vec)
            semantic = scale(raw_sem, cfg.semantic_floor, cfg.semantic_ceiling)
        else:
            semantic = scale(lexical_similarity(profile.embedding_text, job.embedding_text), 0.02, 0.25)
        breakdown = ScoreBreakdown(
            semantic=semantic,
            skills=skill_score(job, profile.skills, cfg.skill_saturation),
            title=title_score(job.title, profile.target_titles),
            recency=recency_score(job.posted_at, now, cfg.max_age_days),
        )
        return ScoredJob(job=job, score=breakdown.total(cfg.weights), breakdown=breakdown)
