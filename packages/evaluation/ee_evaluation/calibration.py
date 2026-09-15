"""Phase 11: learning, calibration and uncertainty.

1. **Prediction quality.** On observed executions: calibration of the learned P(defect) (Brier, log loss, ECE,
   reliability curve) and ranking power (AUROC) of the learned, engineering, hybrid and severity scores.
2. **Tuning without test-set leakage.** Ranking configurations are compared on *development seeds* only. The
   selected configuration is then compared with the default on the *held-out* dataset. A tuned config file is
   written only if it also improves on the held-out data.
3. **Override analysis.** At the engineers' own budget: how much the ranker's selection overlaps with the
   engineers', and the expected hidden defects found by the tests each side chose that the other did not.
4. **Uncertainty.** Bootstrap confidence intervals over decision builds for the headline differences.
"""

from __future__ import annotations

import json
import random
import tempfile
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from statistics import fmean
from typing import Any

from ee_domain.snapshot import DatasetView, build_snapshot
from ee_domain.visibility import visible_data
from ee_etl.importer import read_dataset
from ee_generator import generate_programme, write_programme
from ee_ranking import (
    DecisionContext,
    EngineeringWeights,
    RankingConfig,
    build_context,
    load_ranking_config,
    rank_engineering,
    train_defect_model,
)
from ee_ranking.engineering import engineering_value
from ee_risk import RiskConfig, load_risk_config
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from ee_evaluation.oracle import load_oracle
from ee_evaluation.shadow import ShadowReport, _evaluator, run_shadow_benchmark

DISCLAIMER = (
    "Calibration and tuning study on entirely fictional synthetic data (independent portfolio project)."
)


# --- 1. prediction quality --------------------------------------------------------------------------------------
def expected_calibration_error(probs: list[float], labels: list[int], bins: int = 10) -> float:
    total, ece = len(probs), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(probs) if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if idx:
            ece += len(idx) / total * abs(fmean(probs[i] for i in idx) - fmean(labels[i] for i in idx))
    return round(ece, 4)


def reliability_curve(probs: list[float], labels: list[int], bins: int = 10) -> list[dict[str, float]]:
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(probs) if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if idx:
            out.append(
                {
                    "bin_low": lo,
                    "bin_high": hi,
                    "count": len(idx),
                    "mean_predicted": round(fmean(probs[i] for i in idx), 4),
                    "observed_rate": round(fmean(labels[i] for i in idx), 4),
                }
            )
    return out


@dataclass
class ScoreQuality:
    name: str
    n: int
    positives: int
    auroc: float | None
    brier: float | None = None
    log_loss: float | None = None
    ece: float | None = None


def _auroc(scores: list[float], labels: list[int]) -> float | None:
    return round(float(roc_auc_score(labels, scores)), 4) if 0 < sum(labels) < len(labels) else None


def prediction_quality(
    data: DatasetView,
    builds: list[str] | None = None,
    ranking_config: RankingConfig | None = None,
    risk_config: RiskConfig | None = None,
) -> dict[str, Any]:
    kcfg, rcfg = ranking_config or RankingConfig(), risk_config or RiskConfig()
    ordered = [b.id for b in sorted(data["builds"], key=lambda b: b.sequence)]
    targets = builds or ordered[2:]  # need at least two training builds
    defect_execs = {d.execution_id for d in data["defects"]}
    cache: dict[str, DecisionContext] = {}
    learned, eng, hybrid, severity, labels = [], [], [], [], []
    for b in targets:
        ctx = build_context(build_snapshot(visible_data(data, b), b), rcfg)
        cache[b] = ctx
        model = train_defect_model(data, b, kcfg, cache, rcfg)
        probs = model.predict(ctx)
        feats = {c.key: c for c in ctx.candidates}
        for e in data["executions"]:
            c = feats.get((e.test_id, e.variant_id)) if e.build_id == b else None
            if c is None:
                continue
            value, _ = engineering_value(c, kcfg.weights)
            p = probs[c.key]
            learned.append(p)
            eng.append(value)
            hybrid.append(kcfg.hybrid_engineering * value + kcfg.hybrid_learned * p)
            severity.append(c.max_severity / 5)
            labels.append(int(e.id in defect_execs))
    clipped = [min(max(p, 1e-6), 1 - 1e-6) for p in learned]
    both = 0 < sum(labels) < len(labels)
    return {
        "builds": targets,
        "base_rate": round(fmean(labels), 4) if labels else 0.0,
        "scores": [
            asdict(
                ScoreQuality(
                    "learned_probability",
                    len(labels),
                    sum(labels),
                    _auroc(learned, labels),
                    round(float(brier_score_loss(labels, learned)), 4) if labels else None,
                    round(float(log_loss(labels, clipped, labels=[0, 1])), 4) if both else None,
                    expected_calibration_error(learned, labels) if labels else None,
                )
            ),
            asdict(ScoreQuality("engineering_value", len(labels), sum(labels), _auroc(eng, labels))),
            asdict(ScoreQuality("hybrid_value", len(labels), sum(labels), _auroc(hybrid, labels))),
            asdict(ScoreQuality("severity", len(labels), sum(labels), _auroc(severity, labels))),
        ],
        "reliability_curve": reliability_curve(learned, labels) if labels else [],
    }


# --- 2. tuning on development seeds -------------------------------------------------------------------------------
CHANGE_HEAVY = EngineeringWeights(
    risk_exposure=0.25,
    uncovered=0.20,
    change_relevance=0.25,
    historical_failure=0.15,
    dependency=0.05,
    stale_evidence=0.10,
)


def candidate_configs(base: RankingConfig) -> list[tuple[str, RankingConfig]]:
    out = []
    for wname, weights in (("default_w", base.weights), ("change_heavy_w", CHANGE_HEAVY)):
        for cost in (0.0, 0.15, 0.30):
            for dup in (0.0, 0.20):
                out.append(
                    (
                        f"{wname}|cost={cost}|dup={dup}",
                        replace(
                            base,
                            weights=weights,
                            cost_weight=cost,
                            duplicate_weight=dup,
                            version=f"{base.version}+{wname}-c{cost}-d{dup}",
                        ),
                    )
                )
    return out


def objective(report: ShadowReport) -> float:
    """Critical-defect recall at K=20 plus test-minutes saved while matching the engineers' yield (0 if never matched)."""
    agg = report.aggregate
    recall = agg["at_k"]["risk_based"]["20"]["critical_defect_recall"] or 0.0
    saved = agg["at_engineer_budget"]["risk_based"]["minutes_saved_share"] or 0.0
    return round(recall + saved, 4)


def _headline(report: ShadowReport) -> dict[str, float | None]:
    agg = report.aggregate
    return {
        "objective": objective(report),
        "critical_defect_recall_at_20": agg["at_k"]["risk_based"]["20"]["critical_defect_recall"],
        "critical_risk_coverage_at_budget": agg["at_engineer_budget"]["risk_based"]["critical_risk_coverage"],
        "critical_defect_recall_at_budget": agg["at_engineer_budget"]["risk_based"]["critical_defect_recall"],
        "minutes_saved_share": agg["at_engineer_budget"]["risk_based"]["minutes_saved_share"],
    }


def tune_on_dev_seeds(
    dev_seeds: list[int],
    configs: list[tuple[str, RankingConfig]],
    workdir: Path,
    builds: list[str] | None = None,
    risk_config: RiskConfig | None = None,
) -> dict[str, Any]:
    scores: dict[str, list[float]] = {name: [] for name, _ in configs}
    for seed in dev_seeds:
        ds = write_programme(generate_programme(seed), workdir / f"seed-{seed}")
        gt = ds.parent / "ground_truth" / "ground_truth.json"
        for name, cfg in configs:
            report = run_shadow_benchmark(
                ds,
                gt,
                builds=builds,
                ks=(10, 20),
                random_repeats=1,
                risk_config=risk_config,
                ranking_config=cfg,
            )
            scores[name].append(objective(report))
    mean_scores = {name: round(fmean(v), 4) for name, v in scores.items()}
    best = max(mean_scores, key=lambda n: (mean_scores[n], n))
    return {"dev_seeds": dev_seeds, "objective_by_config": mean_scores, "best": best}


# --- 3. override analysis -------------------------------------------------------------------------------------------
def override_analysis(
    dataset_dir: Path,
    ground_truth: Path,
    builds: list[str] | None = None,
    ranking_config: RankingConfig | None = None,
    risk_config: RiskConfig | None = None,
) -> dict[str, Any]:
    data, _ = read_dataset(dataset_dir)
    oracle = load_oracle(ground_truth, data)
    kcfg, rcfg = ranking_config or load_ranking_config(), risk_config or load_risk_config()
    targets = builds or [b.id for b in sorted(data["builds"], key=lambda b: b.sequence) if b.sequence >= 2]
    per_build: list[dict[str, Any]] = []
    for b in targets:
        ctx = build_context(build_snapshot(visible_data(data, b), b), rcfg)
        keys = {c.key for c in ctx.candidates}
        engineer = [
            (e.test_id, e.variant_id)
            for e in data["executions"]
            if e.build_id == b and (e.test_id, e.variant_id) in keys
        ]
        faults, exposure = oracle.exposure_index(b, [c.key for c in ctx.candidates])
        durations = {c.key: c.duration_min for c in ctx.candidates}
        budget = sum(durations[k] for k in engineer)
        ranker, used = [], 0.0
        for r in rank_engineering(ctx, kcfg):
            k = (r.test_id, r.variant_id)
            if used + durations[k] <= budget + 1e-9:
                ranker.append(k)
                used += durations[k]
        eng_set, rank_set = set(engineer), set(ranker)

        def expected(
            sel: set[tuple[str, str]],
            ctx: DecisionContext = ctx,
            faults: Any = faults,
            exposure: Any = exposure,
        ) -> float:
            ev = _evaluator(ctx, faults, exposure)
            for k in sorted(sel):
                ev.add(k)
            return round(ev.expected_defects, 4)

        per_build.append(
            {
                "build_id": b,
                "engineer_tests": len(eng_set),
                "ranker_tests": len(rank_set),
                "jaccard": round(len(eng_set & rank_set) / max(len(eng_set | rank_set), 1), 4),
                "override_share": round(len(eng_set - rank_set) / max(len(eng_set), 1), 4),
                "expected_defects_engineer_only": expected(eng_set - rank_set),
                "expected_defects_ranker_only": expected(rank_set - eng_set),
                "expected_defects_shared": expected(eng_set & rank_set),
                "live_faults": len(faults),
            }
        )
    return {
        "builds": per_build,
        "mean_jaccard": round(fmean(p["jaccard"] for p in per_build), 4),
        "mean_override_share": round(fmean(p["override_share"] for p in per_build), 4),
        "mean_expected_defects_engineer_only": round(
            fmean(p["expected_defects_engineer_only"] for p in per_build), 4
        ),
        "mean_expected_defects_ranker_only": round(
            fmean(p["expected_defects_ranker_only"] for p in per_build), 4
        ),
    }


# --- 4. bootstrap uncertainty ---------------------------------------------------------------------------------------
def bootstrap_ci(
    values: list[float], iterations: int = 2000, seed: int = 0, alpha: float = 0.05
) -> dict[str, float]:
    rng = random.Random(seed)
    means = sorted(fmean(rng.choices(values, k=len(values))) for _ in range(iterations))
    lo, hi = means[int(alpha / 2 * iterations)], means[int((1 - alpha / 2) * iterations) - 1]
    return {
        "mean": round(fmean(values), 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "n": len(values),
    }


def build_level_differences(report: ShadowReport) -> dict[str, dict[str, float]]:
    crit = [
        (b.at_engineer_budget["risk_based"]["critical_defect_recall"] or 0.0)
        - b.engineer["critical_defect_recall"]
        for b in report.builds
    ]
    cov = [
        (b.at_engineer_budget["risk_based"]["critical_risk_coverage"] or 0.0)
        - b.engineer["critical_risk_coverage"]
        for b in report.builds
    ]
    saved = [b.at_engineer_budget["risk_based"]["minutes_saved_share"] or 0.0 for b in report.builds]
    return {
        "critical_defect_recall_minus_engineer": bootstrap_ci(crit),
        "critical_risk_coverage_minus_engineer": bootstrap_ci(cov),
        "minutes_saved_share": bootstrap_ci(saved),
    }


# --- orchestration ------------------------------------------------------------------------------------------------
@dataclass
class CalibrationReport:
    heldout_seed: int | None
    prediction_quality: dict[str, Any]
    tuning: dict[str, Any]
    heldout_default: dict[str, float | None]
    heldout_tuned: dict[str, float | None]
    tuned_improves_heldout: bool
    uncertainty: dict[str, dict[str, float]]
    overrides: dict[str, Any]
    sentence: str = ""
    findings: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def run_calibration(
    dataset_dir: Path,
    ground_truth: Path,
    dev_seeds: list[int] | None = None,
    configs: list[tuple[str, RankingConfig]] | None = None,
    builds: list[str] | None = None,
    random_repeats: int = 5,
    workdir: Path | None = None,
) -> CalibrationReport:
    data, manifest = read_dataset(dataset_dir)
    heldout_seed = manifest.get("seed")
    dev = [s for s in (dev_seeds or [1, 2, 3]) if s != heldout_seed]
    base, rcfg = load_ranking_config(), load_risk_config()
    cands = configs or candidate_configs(base)
    with tempfile.TemporaryDirectory() as tmp:
        tuning = tune_on_dev_seeds(dev, cands, workdir or Path(tmp), builds, rcfg)
    best_cfg = dict(cands)[tuning["best"]]
    default_report = run_shadow_benchmark(
        dataset_dir,
        ground_truth,
        builds=builds,
        ks=(10, 20),
        random_repeats=random_repeats,
        risk_config=rcfg,
        ranking_config=base,
    )
    tuned_report = run_shadow_benchmark(
        dataset_dir,
        ground_truth,
        builds=builds,
        ks=(10, 20),
        random_repeats=random_repeats,
        risk_config=rcfg,
        ranking_config=best_cfg,
    )
    heldout_default, heldout_tuned = _headline(default_report), _headline(tuned_report)
    improves = (heldout_tuned["objective"] or 0) > (heldout_default["objective"] or 0) + 1e-9
    quality = prediction_quality(data, builds, base, rcfg)
    overrides = override_analysis(dataset_dir, ground_truth, builds, base, rcfg)
    uncertainty = build_level_differences(default_report)

    report = CalibrationReport(
        heldout_seed, quality, tuning, heldout_default, heldout_tuned, improves, uncertainty, overrides
    )
    scores = {s["name"]: s for s in quality["scores"]}
    diff = uncertainty["critical_defect_recall_minus_engineer"]
    report.sentence = (
        f"On held-out seed {heldout_seed}, the learned defect model reached AUROC {scores['learned_probability']['auroc']} "
        f"(ECE {scores['learned_probability']['ece']}) versus {scores['engineering_value']['auroc']} for the engineering score; "
        f"the configuration selected on development seeds {dev} ({tuning['best']}) "
        f"{'improved' if improves else 'did not improve'} the held-out objective ({heldout_default['objective']} → {heldout_tuned['objective']}); "
        f"risk-based minus engineer critical-defect recall at equal budget was {diff['mean']:+.3f} "
        f"(95% bootstrap CI {diff['ci_low']:+.3f} to {diff['ci_high']:+.3f}, n={diff['n']} builds)."
    )
    findings = []
    if (scores["learned_probability"]["auroc"] or 0) < (scores["engineering_value"]["auroc"] or 0):
        findings.append(
            "The learned model ranks observed defects worse than the deterministic engineering score; hybrid weighting should stay conservative."
        )
    if diff["ci_low"] <= 0 <= diff["ci_high"]:
        findings.append(
            "The critical-defect-recall difference versus engineers at equal budget is not distinguishable from zero across builds."
        )
    if not improves:
        findings.append(
            "Tuning on development seeds did not transfer to the held-out seed; the committed default configuration is kept."
        )
    o = overrides
    findings.append(
        f"At equal budget the ranker would override {o['mean_override_share']:.0%} of engineer choices "
        f"(Jaccard {o['mean_jaccard']:.2f}); tests only engineers chose held {o['mean_expected_defects_engineer_only']:.2f} expected hidden defects per build versus "
        f"{o['mean_expected_defects_ranker_only']:.2f} for tests only the ranker chose."
    )
    report.findings = findings
    return report


def calibration_markdown(r: CalibrationReport) -> str:
    q = r.prediction_quality
    lines = [
        "# Learning & Calibration Study",
        "",
        f"> {r.disclaimer}",
        "",
        f"**Result:** {r.sentence}",
        "",
        "## Findings (generated)",
        "",
        *[f"- {f}" for f in r.findings],
        "",
        f"## Prediction quality on observed executions (builds {', '.join(q['builds'])}, base rate {q['base_rate']:.1%})",
        "",
        "| Score | n | Positives | AUROC | Brier | Log loss | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in q["scores"]:
        lines.append(
            f"| {s['name']} | {s['n']} | {s['positives']} | {s['auroc']} | {s['brier'] if s['brier'] is not None else '—'} | {s['log_loss'] if s['log_loss'] is not None else '—'} | {s['ece'] if s['ece'] is not None else '—'} |"
        )
    lines += [
        "",
        "### Reliability curve (learned probability)",
        "",
        "| Bin | Count | Mean predicted | Observed rate |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| {c['bin_low']:.1f}–{c['bin_high']:.1f} | {c['count']} | {c['mean_predicted']:.3f} | {c['observed_rate']:.3f} |"
        for c in q["reliability_curve"]
    ]
    lines += [
        "",
        f"## Tuning on development seeds {r.tuning['dev_seeds']} (never on the held-out seed)",
        "",
        "| Configuration | Mean dev objective |",
        "|---|---:|",
    ]
    lines += [
        f"| {'**' + n + '**' if n == r.tuning['best'] else n} | {v:.4f} |"
        for n, v in sorted(r.tuning["objective_by_config"].items(), key=lambda kv: -kv[1])
    ]
    lines += [
        "",
        f"## Held-out seed {r.heldout_seed}: default vs. selected configuration",
        "",
        "| Metric | Default | Selected |",
        "|---|---:|---:|",
    ]
    lines += [f"| {k} | {r.heldout_default[k]} | {r.heldout_tuned[k]} |" for k in r.heldout_default]
    lines += [
        "",
        "## Bootstrap uncertainty over decision builds (default configuration)",
        "",
        "| Quantity | Mean | 95% CI | n |",
        "|---|---:|---|---:|",
    ]
    lines += [
        f"| {k} | {v['mean']:+.4f} | {v['ci_low']:+.4f} … {v['ci_high']:+.4f} | {v['n']} |"
        for k, v in r.uncertainty.items()
    ]
    lines += [
        "",
        "## Engineer vs. ranker overrides at equal budget",
        "",
        "| Build | Engineer tests | Ranker tests | Jaccard | Override share | Exp. defects engineer-only | Exp. defects ranker-only | Shared |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {b['build_id']} | {b['engineer_tests']} | {b['ranker_tests']} | {b['jaccard']:.2f} | {b['override_share']:.0%} | {b['expected_defects_engineer_only']:.2f} | {b['expected_defects_ranker_only']:.2f} | {b['expected_defects_shared']:.2f} |"
        for b in r.overrides["builds"]
    ]
    return "\n".join(lines) + "\n"


def write_calibration_report(
    report: CalibrationReport,
    out_dir: Path,
    tuned_config_path: Path | None = None,
    tuned: RankingConfig | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(asdict(report), indent=1), encoding="utf-8")
    md = out_dir / "latest.md"
    md.write_text(calibration_markdown(report), encoding="utf-8")
    if report.tuned_improves_heldout and tuned_config_path is not None and tuned is not None:
        w = tuned.weights
        tuned_config_path.write_text(
            f"# Selected on development seeds, improves held-out seed {report.heldout_seed}. Not the default.\n"
            f'version = "{tuned.version}"\n\n[weights]\n'
            + "".join(
                f"{k} = {getattr(w, k)}\n"
                for k in (
                    "risk_exposure",
                    "uncovered",
                    "change_relevance",
                    "historical_failure",
                    "dependency",
                    "stale_evidence",
                )
            )
            + f"\n[penalties]\ncost_weight = {tuned.cost_weight}\nduplicate_weight = {tuned.duplicate_weight}\n\n"
            f"[hybrid]\nengineering = {tuned.hybrid_engineering}\nlearned = {tuned.hybrid_learned}\n",
            encoding="utf-8",
        )
    return md
