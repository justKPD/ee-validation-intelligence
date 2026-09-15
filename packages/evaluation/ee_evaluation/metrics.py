"""Pure metric functions and an incremental selection evaluator."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from ee_evaluation.oracle import HiddenFault, Key


def dcg(relevances: Sequence[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(ranked_relevances: Sequence[float], all_relevances: Sequence[float], k: int) -> float:
    ideal = dcg(sorted(all_relevances, reverse=True)[:k])
    return dcg(ranked_relevances[:k]) / ideal if ideal > 0 else 0.0


def average_precision_at_k(ranked_binary: Sequence[bool], total_relevant: int, k: int) -> float:
    hits, total = 0, 0.0
    for i, rel in enumerate(ranked_binary[:k]):
        if rel:
            hits += 1
            total += hits / (i + 1)
    denom = min(total_relevant, k)
    return total / denom if denom else 0.0


@dataclass
class SelectionEvaluator:
    """Tracks expected detections and coverage as (test, variant) pairs are added to a selection."""

    faults: list[HiddenFault]
    exposure: dict[Key, list[tuple[int, float]]]
    pair_requirements: dict[Key, tuple[str, ...]]
    durations: dict[Key, float]
    critical_weights: dict[tuple[str, str], float]
    need_pairs: set[tuple[str, str]]
    miss: list[float] = field(init=False)
    minutes: float = field(init=False, default=0.0)
    count: int = field(init=False, default=0)
    covered_critical: set[tuple[str, str]] = field(init=False, default_factory=set)
    covered_need: set[tuple[str, str]] = field(init=False, default_factory=set)

    def __post_init__(self) -> None:
        self.miss = [1.0] * len(self.faults)

    def add(self, key: Key) -> None:
        for i, sens in self.exposure.get(key, []):
            self.miss[i] *= 1.0 - sens
        self.minutes += self.durations[key]
        self.count += 1
        for req in self.pair_requirements[key]:
            pair = (req, key[1])
            if pair in self.critical_weights:
                self.covered_critical.add(pair)
            if pair in self.need_pairs:
                self.covered_need.add(pair)

    @property
    def expected_defects(self) -> float:
        return sum(1.0 - m for m in self.miss)

    def summary(self) -> dict[str, float]:
        n_crit = sum(1 for f in self.faults if f.critical)
        crit_found = sum(1.0 - m for f, m in zip(self.faults, self.miss, strict=True) if f.critical)
        total_w = sum(self.critical_weights.values())
        crit_cov = sum(self.critical_weights[p] for p in self.covered_critical) / total_w if total_w else 0.0
        need_cov = len(self.covered_need) / len(self.need_pairs) if self.need_pairs else 0.0
        minutes = self.minutes
        return {
            "tests_selected": self.count,
            "minutes": round(minutes, 1),
            "expected_defects": round(self.expected_defects, 4),
            "defect_recall": round(self.expected_defects / len(self.faults), 4) if self.faults else 0.0,
            "critical_defect_recall": round(crit_found / n_crit, 4) if n_crit else 0.0,
            "critical_risk_coverage": round(crit_cov, 4),
            "coverage_gain": round(need_cov, 4),
            "risk_coverage_per_hour": round(crit_cov / (minutes / 60), 4) if minutes else 0.0,
            "coverage_gain_per_hour": round(need_cov / (minutes / 60), 4) if minutes else 0.0,
        }
