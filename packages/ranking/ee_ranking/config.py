from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from ee_domain.db import REPO_ROOT

DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "ranking.toml"


@dataclass(frozen=True)
class EngineeringWeights:
    risk_exposure: float = 0.30
    uncovered: float = 0.25
    change_relevance: float = 0.15
    historical_failure: float = 0.15
    dependency: float = 0.05
    stale_evidence: float = 0.10

    def __post_init__(self) -> None:
        values = [getattr(self, f.name) for f in fields(self)]
        if abs(sum(values) - 1.0) > 1e-6 or min(values) < 0:
            raise ValueError(
                f"engineering weights must be non-negative and sum to 1.0, got {sum(values):.4f}"
            )


@dataclass(frozen=True)
class RankingConfig:
    weights: EngineeringWeights = field(default_factory=EngineeringWeights)
    cost_weight: float = 0.15
    duplicate_weight: float = 0.20
    hybrid_engineering: float = 0.65
    hybrid_learned: float = 0.35
    min_positive_labels: int = 5
    version: str = "ranking-1.0"

    def __post_init__(self) -> None:
        if abs(self.hybrid_engineering + self.hybrid_learned - 1.0) > 1e-6:
            raise ValueError("hybrid weights must sum to 1.0")


def load_ranking_config(path: Path | None = None) -> RankingConfig:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return RankingConfig()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    pen, hyb, model = raw.get("penalties", {}), raw.get("hybrid", {}), raw.get("model", {})
    return RankingConfig(
        weights=EngineeringWeights(**raw.get("weights", {})),
        cost_weight=pen.get("cost_weight", 0.15),
        duplicate_weight=pen.get("duplicate_weight", 0.20),
        hybrid_engineering=hyb.get("engineering", 0.65),
        hybrid_learned=hyb.get("learned", 0.35),
        min_positive_labels=model.get("min_positive_labels", 5),
        version=raw.get("version", "ranking-1.0"),
    )
