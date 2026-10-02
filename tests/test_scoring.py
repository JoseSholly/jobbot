from datetime import UTC, datetime, timedelta

import numpy as np

from jobbot.services.rerank import FeedbackReranker
from jobbot.services.scoring import (
    DEFAULT_WEIGHTS,
    Scorer,
    ScoringConfig,
    recency_score,
    skill_score,
    title_score,
)
from tests.fakes import FakeEmbedder, job

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def test_title_score():
    assert title_score("Senior Backend Engineer (Python)", ["Backend Engineer"]) == 1.0
    assert title_score("Backend Developer", ["Backend Engineer"]) > 0.4
    assert title_score("Accountant", ["Backend Engineer"]) < 0.3
    assert title_score("Anything", []) == 0.0


def test_skill_score_saturates():
    j = job(description="Python Django PostgreSQL Docker Redis Celery")
    assert skill_score(j, ["Python", "Django", "PostgreSQL", "Docker", "Redis", "Go"], 5) == 1.0
    assert skill_score(j, ["Rust"], 5) == 0.0
    assert skill_score(j, ["Python", "Rust"], 5) == 0.5


def test_recency():
    assert recency_score(NOW, NOW, 14) == 1.0
    assert recency_score(NOW - timedelta(days=7), NOW, 14) == 0.5
    assert recency_score(None, NOW, 14) == 0.3


def test_relevant_job_outscores_irrelevant(backend_profile):
    scorer = Scorer(ScoringConfig(weights=DEFAULT_WEIGHTS))
    emb = FakeEmbedder()
    good = job(
        "Senior Backend Engineer (Python)",
        posted_at=NOW,
        description="Python Django DRF PostgreSQL Docker REST APIs",
    )
    bad = job("Sales Representative", posted_at=NOW, description="Cold calling and CRM")
    pv, gv, bv = (
        np.asarray(v)
        for v in emb.embed([backend_profile.embedding_text, good.embedding_text, bad.embedding_text])
    )
    s_good = scorer.score(good, backend_profile, NOW, pv, gv)
    s_bad = scorer.score(bad, backend_profile, NOW, pv, bv)
    assert s_good.score > 50 > s_bad.score
    assert 0 <= s_bad.score <= 100


def test_lexical_fallback_without_vectors(backend_profile):
    scorer = Scorer(ScoringConfig(weights=DEFAULT_WEIGHTS))
    good = job("Python Developer", posted_at=NOW, description="Django PostgreSQL APIs Docker")
    assert scorer.score(good, backend_profile, NOW, None, None).breakdown.semantic > 0


def test_reranker_boosts_similar_to_saved_and_penalizes_dismissed():
    r = FeedbackReranker(max_adjust=10)
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert r.adjustment(a, np.array([a]), None) == 10
    assert r.adjustment(a, None, np.array([a])) == -10
    assert r.adjustment(a, np.array([b]), None) == 0  # unrelated history doesn't move it
