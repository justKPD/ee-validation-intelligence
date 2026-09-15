"""Deterministic engineering ranker with greedy duplicate-evidence and cost penalties.

    value(c)    = Σ w_f · feature_f(c)
    priority(c) = value(c) − cost_weight · duration/max_duration − duplicate_weight · share of c's
                  (requirement, variant) pairs already covered by higher-ranked tests

Tests are picked greedily, so the duplicate penalty reflects what earlier picks already cover.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from ee_ranking.config import EngineeringWeights, RankingConfig
from ee_ranking.features import CandidateFeatures, DecisionContext

Key = tuple[str, str]


@dataclass(frozen=True)
class RankedTest:
    rank: int
    test_id: str
    variant_id: str
    strategy: str
    score: float
    value: float
    cost_penalty: float
    duplicate_penalty: float
    duration_min: float
    cumulative_minutes: float
    contributions: dict[str, float]
    learned_probability: float | None
    critical: bool
    requirement_ids: list[str]
    component_ids: list[str]
    reasons: list[str]
    evidence_ids: list[str]


WEIGHTED_FEATURES = tuple(f.name for f in fields(EngineeringWeights))


def engineering_value(c: CandidateFeatures, w: EngineeringWeights) -> tuple[float, dict[str, float]]:
    contributions = {name: getattr(w, name) * float(getattr(c, name)) for name in WEIGHTED_FEATURES}
    return sum(contributions.values()), contributions


def greedy_rank(
    ctx: DecisionContext,
    values: dict[Key, float],
    contributions: dict[Key, dict[str, float]],
    strategy: str,
    config: RankingConfig,
    learned: dict[Key, float] | None = None,
    limit: int | None = None,
) -> list[RankedTest]:
    max_dur = ctx.max_duration
    remaining: dict[Key, CandidateFeatures] = {c.key: c for c in ctx.candidates}
    covered: set[tuple[str, str]] = set()
    n = len(remaining) if limit is None else min(limit, len(remaining))
    out: list[RankedTest] = []
    minutes = 0.0
    while len(out) < n:
        best: tuple[float, float] | None = None
        pick: CandidateFeatures | None = None
        pick_terms = (0.0, 0.0)
        for key, c in remaining.items():
            pairs = [(r, c.variant_id) for r in c.requirement_ids]
            dup = sum(p in covered for p in pairs) / len(pairs)
            cost_pen = config.cost_weight * c.duration_min / max_dur
            dup_pen = config.duplicate_weight * dup
            order = (values[key] - cost_pen - dup_pen, -c.duration_min)
            if best is None or order > best:
                best, pick, pick_terms = order, c, (cost_pen, dup_pen)
        assert pick is not None and best is not None
        del remaining[pick.key]
        covered.update((r, pick.variant_id) for r in pick.requirement_ids)
        minutes += pick.duration_min
        out.append(
            RankedTest(
                rank=len(out) + 1,
                test_id=pick.test_id,
                variant_id=pick.variant_id,
                strategy=strategy,
                score=round(best[0], 4),
                value=round(values[pick.key], 4),
                cost_penalty=round(pick_terms[0], 4),
                duplicate_penalty=round(pick_terms[1], 4),
                duration_min=pick.duration_min,
                cumulative_minutes=round(minutes, 1),
                contributions={k: round(v, 4) for k, v in contributions[pick.key].items()},
                learned_probability=None if learned is None else learned[pick.key],
                critical=pick.critical,
                requirement_ids=list(pick.requirement_ids),
                component_ids=list(pick.component_ids),
                reasons=list(pick.reasons),
                evidence_ids=list(pick.evidence_ids),
            )
        )
    return out


def rank_engineering(
    ctx: DecisionContext, config: RankingConfig | None = None, limit: int | None = None
) -> list[RankedTest]:
    cfg = config or RankingConfig()
    values: dict[Key, float] = {}
    contributions: dict[Key, dict[str, float]] = {}
    for c in ctx.candidates:
        values[c.key], contributions[c.key] = engineering_value(c, cfg.weights)
    return greedy_rank(ctx, values, contributions, "risk_based", cfg, None, limit)
