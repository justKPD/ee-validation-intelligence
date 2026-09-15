"""Learned P(test reveals defect | context), trained only on builds before the decision build.

The model supplements engineering risk and never replaces it:
``hybrid = hybrid_engineering · engineering_value + hybrid_learned · P(defect)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ee_domain.snapshot import DatasetView, build_snapshot
from ee_domain.visibility import visible_data
from ee_risk import RiskConfig
from sklearn.ensemble import HistGradientBoostingClassifier

from ee_ranking.config import RankingConfig
from ee_ranking.engineering import Key, RankedTest, engineering_value, greedy_rank
from ee_ranking.features import FEATURE_NAMES, DecisionContext, build_context


@dataclass
class DefectProbabilityModel:
    build_id: str
    trained_on_builds: list[str]
    n_samples: int
    n_positive: int
    prior: float
    estimator: Any | None = field(default=None, repr=False)
    feature_names: tuple[str, ...] = FEATURE_NAMES
    model_version: str = "hgb-defect-1.0"

    @property
    def trained(self) -> bool:
        return self.estimator is not None

    def predict(self, ctx: DecisionContext) -> dict[Key, float]:
        if self.estimator is None:
            return {c.key: round(self.prior, 4) for c in ctx.candidates}
        rows = [c.vector(ctx.max_duration) for c in ctx.candidates]
        probs = self.estimator.predict_proba(rows)[:, 1]
        return {c.key: round(float(p), 4) for c, p in zip(ctx.candidates, probs, strict=True)}

    def info(self) -> dict[str, Any]:
        return {
            "build_id": self.build_id,
            "trained": self.trained,
            "trained_on_builds": self.trained_on_builds,
            "n_samples": self.n_samples,
            "n_positive": self.n_positive,
            "prior": round(self.prior, 4),
            "model_version": self.model_version,
        }


def train_defect_model(
    data: DatasetView,
    build_id: str,
    config: RankingConfig | None = None,
    context_cache: dict[str, DecisionContext] | None = None,
    risk_config: RiskConfig | None = None,
) -> DefectProbabilityModel:
    cfg = config or RankingConfig()
    cache = context_cache if context_cache is not None else {}
    visible = visible_data(data, build_id)
    decision = build_snapshot(visible, build_id)
    defect_execs = {d.execution_id for d in decision.defects}

    x: list[list[float]] = []
    y: list[int] = []
    builds: list[str] = []
    for b in sorted(decision.builds.values(), key=lambda b: b.sequence):
        if b.sequence >= decision.sequence:
            continue
        if b.id not in cache:
            cache[b.id] = build_context(build_snapshot(visible, b.id), risk_config)
        ctx = cache[b.id]
        feats = {c.key: c for c in ctx.candidates}
        for e in decision.executions:
            c = feats.get((e.test_id, e.variant_id)) if e.build_id == b.id else None
            if c is not None:
                x.append(c.vector(ctx.max_duration))
                y.append(int(e.id in defect_execs))
        builds.append(b.id)

    n_pos = sum(y)
    prior = n_pos / len(y) if y else 0.0
    model = DefectProbabilityModel(build_id, builds, len(y), n_pos, prior)
    if n_pos >= cfg.min_positive_labels and len(y) - n_pos >= cfg.min_positive_labels:
        est = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_depth=3, random_state=0)
        est.fit(x, y)
        model.estimator = est
    return model


def rank_hybrid(
    ctx: DecisionContext,
    model: DefectProbabilityModel,
    config: RankingConfig | None = None,
    limit: int | None = None,
) -> list[RankedTest]:
    cfg = config or RankingConfig()
    probs = model.predict(ctx)
    values: dict[Key, float] = {}
    contributions: dict[Key, dict[str, float]] = {}
    for c in ctx.candidates:
        value, contrib = engineering_value(c, cfg.weights)
        values[c.key] = cfg.hybrid_engineering * value + cfg.hybrid_learned * probs[c.key]
        contributions[c.key] = {k: cfg.hybrid_engineering * v for k, v in contrib.items()}
        contributions[c.key]["learned_defect_probability"] = cfg.hybrid_learned * probs[c.key]
    return greedy_rank(ctx, values, contributions, "hybrid", cfg, probs, limit)
