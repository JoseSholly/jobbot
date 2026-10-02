"""Pick the final N jobs for a message, honouring the Nigeria/global quota."""

from __future__ import annotations

from jobbot.domain.models import Region, ScoredJob


def select(scored: list[ScoredJob], ng_quota: int, global_quota: int, min_score: float) -> list[ScoredJob]:
    """Take the best `ng_quota` NG and `global_quota` GLOBAL jobs at/above `min_score`.

    If one side is short, the remaining slots are filled from the other side.
    The result is ordered by score (best first).
    """
    eligible = sorted((s for s in scored if s.score >= min_score), key=lambda s: s.score, reverse=True)
    ng = [s for s in eligible if s.job.region is Region.NG]
    gl = [s for s in eligible if s.job.region is Region.GLOBAL]

    picked_ng = ng[:ng_quota]
    picked_gl = gl[:global_quota]
    total = ng_quota + global_quota
    missing = total - len(picked_ng) - len(picked_gl)
    if missing > 0:
        if len(picked_ng) < ng_quota:
            picked_gl = gl[: global_quota + missing]
        else:
            picked_ng = ng[: ng_quota + missing]
    picked = picked_ng + picked_gl
    return sorted(picked, key=lambda s: s.score, reverse=True)[:total]
