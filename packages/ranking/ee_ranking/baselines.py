"""Baselines: static severity-first prioritisation and seeded random selection."""

from __future__ import annotations

import random

from ee_ranking.engineering import RankedTest
from ee_ranking.features import CandidateFeatures, DecisionContext


def _plain(ordered: list[CandidateFeatures], strategy: str, scores: list[float]) -> list[RankedTest]:
    out, minutes = [], 0.0
    for i, (c, s) in enumerate(zip(ordered, scores, strict=True), start=1):
        minutes += c.duration_min
        out.append(
            RankedTest(
                rank=i,
                test_id=c.test_id,
                variant_id=c.variant_id,
                strategy=strategy,
                score=round(s, 4),
                value=round(s, 4),
                cost_penalty=0.0,
                duplicate_penalty=0.0,
                duration_min=c.duration_min,
                cumulative_minutes=round(minutes, 1),
                contributions={},
                learned_probability=None,
                critical=c.critical,
                requirement_ids=list(c.requirement_ids),
                component_ids=list(c.component_ids),
                reasons=[f"baseline: {strategy}"],
                evidence_ids=list(c.evidence_ids),
            )
        )
    return out


def rank_severity(ctx: DecisionContext) -> list[RankedTest]:
    """Historical/static prioritisation: highest linked requirement severity first."""
    ordered = sorted(ctx.candidates, key=lambda c: (-c.max_severity, c.test_id, c.variant_id))
    return _plain(ordered, "severity_baseline", [c.max_severity / 5 for c in ordered])


def rank_random(ctx: DecisionContext, seed: int = 0) -> list[RankedTest]:
    ordered = sorted(ctx.candidates, key=lambda c: c.key)
    random.Random(seed).shuffle(ordered)
    n = len(ordered)
    return _plain(ordered, "random_baseline", [1 - i / max(n, 1) for i in range(n)])
