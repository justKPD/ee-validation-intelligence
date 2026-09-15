from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from ee_domain.db import REPO_ROOT

DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "risk.toml"


def _check_sum(obj: Any, label: str) -> None:
    total = sum(getattr(obj, f.name) for f in fields(obj))
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{label} must sum to 1.0, got {total:.4f}")
    if any(getattr(obj, f.name) < 0 for f in fields(obj)):
        raise ValueError(f"{label} must be non-negative")


@dataclass(frozen=True)
class RiskWeights:
    base: float = 0.35
    recent_change: float = 0.20
    historical_failure: float = 0.15
    dependency: float = 0.10
    evidence_staleness: float = 0.10
    variant_exposure: float = 0.10

    def __post_init__(self) -> None:
        _check_sum(self, "risk weights")


@dataclass(frozen=True)
class RequirementWeights:
    fmea_base: float = 0.40
    component_risk: float = 0.40
    revised_in_build: float = 0.20

    def __post_init__(self) -> None:
        _check_sum(self, "requirement weights")


@dataclass(frozen=True)
class RiskConfig:
    weights: RiskWeights = field(default_factory=RiskWeights)
    requirement_weights: RequirementWeights = field(default_factory=RequirementWeights)
    failure_prior_alpha: float = 1.0
    failure_prior_beta: float = 9.0
    failure_rate_saturation: float = 0.30
    dependency_propagation: float = 0.70
    requirement_revision_change_signal: float = 0.60
    confidence_half_evidence: int = 20
    disagreement_threshold: float = 0.45
    max_evidence_age_days: int = 35
    version: str = "risk-1.0"


def load_risk_config(path: Path | None = None) -> RiskConfig:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return RiskConfig()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return RiskConfig(
        weights=RiskWeights(**raw.get("weights", {})),
        requirement_weights=RequirementWeights(**raw.get("requirement_weights", {})),
        max_evidence_age_days=raw.get("coverage", {}).get("max_evidence_age_days", 35),
        version=raw.get("version", "risk-1.0"),
        **raw.get("parameters", {}),
    )
