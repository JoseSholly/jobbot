from jobbot.domain.models import Region, ScoreBreakdown, ScoredJob
from jobbot.services.selection import select
from tests.fakes import job


def scored(n, region, score):
    j = job(f"Job {region} {n}", f"Co{region}{n}")
    j.region = region
    return ScoredJob(job=j, score=score, breakdown=ScoreBreakdown(0, 0, 0, 0))


def test_quota_respected():
    items = [scored(i, Region.NG, 90 - i) for i in range(10)] + [
        scored(i, Region.GLOBAL, 95 - i) for i in range(10)
    ]
    picked = select(items, 4, 6, 50)
    assert len(picked) == 10
    assert sum(p.job.region is Region.NG for p in picked) == 4
    assert [p.score for p in picked] == sorted((p.score for p in picked), reverse=True)


def test_fill_from_other_side_when_short():
    items = [scored(i, Region.NG, 80) for i in range(1)] + [scored(i, Region.GLOBAL, 70) for i in range(20)]
    picked = select(items, 4, 6, 50)
    assert len(picked) == 10
    assert sum(p.job.region is Region.NG for p in picked) == 1

    items = [scored(i, Region.NG, 80) for i in range(20)] + [scored(0, Region.GLOBAL, 70)]
    picked = select(items, 4, 6, 50)
    assert sum(p.job.region is Region.NG for p in picked) == 9


def test_min_score_can_return_fewer():
    items = [scored(i, Region.GLOBAL, 40 + i * 5) for i in range(5)]  # 40..60
    picked = select(items, 4, 6, 50)
    assert [round(p.score) for p in picked] == [60, 55, 50]
