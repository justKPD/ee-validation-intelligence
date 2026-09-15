"""Shadow Test Planning benchmark.

For every historical build B (B002…), the decision point is reconstructed from ``visible_data(data, B)``.
Each strategy ranks all candidate (test, variant) pairs without seeing B's results. Rankings are then scored:

1. **Counterfactual (oracle) scoring** at cut-offs K and at the historical engineers' own minute budget,
   using hidden ground-truth faults. This works for tests that were never run.
2. **Observed replay**: strategies only reorder the tests engineers actually ran in B, scored against
   observed defects (no oracle).

No number is hard-coded; the summary sentence is formatted from the aggregate of the run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any

from ee_domain.snapshot import build_snapshot
from ee_domain.visibility import visible_data
from ee_etl.importer import read_dataset
from ee_generator import GENERATOR_VERSION
from ee_ranking import (
    DecisionContext,
    RankedTest,
    RankingConfig,
    build_context,
    load_ranking_config,
    rank_engineering,
    rank_hybrid,
    rank_random,
    rank_severity,
    train_defect_model,
)
from ee_risk import RiskConfig, load_risk_config

from ee_evaluation.metrics import SelectionEvaluator, average_precision_at_k, ndcg_at_k
from ee_evaluation.oracle import Key, Oracle, load_oracle

DISCLAIMER = (
    "Synthetic benchmark on entirely fictional data from an independent portfolio project. "
    "Results must not be interpreted as performance of any real or BMW Group validation process."
)
RANKED_STRATEGIES = ("risk_based", "hybrid", "severity_baseline")
ALL_STRATEGIES = (*RANKED_STRATEGIES, "random_baseline")


@dataclass
class BuildResult:
    build_id: str
    candidates: int
    live_faults: int
    critical_live_faults: int
    engineer_budget_minutes: float
    engineer: dict[str, float]
    at_k: dict[str, dict[str, dict[str, float]]]
    at_engineer_budget: dict[str, dict[str, float | None]]
    observed_replay: dict[str, float | None]
    model: dict[str, Any]


@dataclass
class ShadowReport:
    seed: int | None
    generator_version: str
    risk_config_version: str
    ranking_config_version: str
    ks: list[int]
    random_repeats: int
    builds: list[BuildResult]
    aggregate: dict[str, Any] = field(default_factory=dict)
    sentence: str = ""
    findings: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def _evaluator(ctx: DecisionContext, faults: Any, exposure: Any) -> SelectionEvaluator:
    critical_weights, need = {}, set()
    for (rid, vid), rec in ctx.evidence.items():
        if rec.status.value == "CURRENT":
            continue
        need.add((rid, vid))
        req = ctx.snapshot.requirements[rid]
        if ctx.requirement_risk[rid].critical:
            critical_weights[(rid, vid)] = float(req.severity * req.fmea_impact)
    return SelectionEvaluator(
        faults=faults,
        exposure=exposure,
        pair_requirements={c.key: c.requirement_ids for c in ctx.candidates},
        durations={c.key: c.duration_min for c in ctx.candidates},
        critical_weights=critical_weights,
        need_pairs=need,
    )


def _score_ranking(
    order: list[Key],
    ctx: DecisionContext,
    faults: Any,
    exposure: dict[Key, list[tuple[int, float]]],
    ks: list[int],
    budget: float,
    engineer_yield: float,
    engineer_keys: list[Key],
    observed_defect_keys: set[Key],
) -> tuple[dict[str, dict[str, float]], dict[str, float | None], float | None]:
    severity = [f.severity for f in faults]
    relevance = {k: sum(s * severity[i] for i, s in hits) for k, hits in exposure.items()}
    all_rel = [relevance.get(c.key, 0.0) for c in ctx.candidates]
    ranked_rel = [relevance.get(k, 0.0) for k in order]
    n_relevant = sum(1 for r in all_rel if r > 0)

    at_k: dict[str, dict[str, float]] = {}
    ev = _evaluator(ctx, faults, exposure)
    minutes_to_match: float | None = None
    for i, key in enumerate(order, start=1):
        ev.add(key)
        if minutes_to_match is None and ev.expected_defects >= engineer_yield - 1e-9:
            minutes_to_match = round(ev.minutes, 1)
        if i in ks:
            s = ev.summary()
            s["ndcg"] = round(ndcg_at_k(ranked_rel, all_rel, i), 4)
            s["map"] = round(average_precision_at_k([r > 0 for r in ranked_rel], n_relevant, i), 4)
            at_k[str(i)] = s

    bev = _evaluator(ctx, faults, exposure)
    for key in order:  # budget fill: skip tests that no longer fit, keep filling
        if bev.minutes + bev.durations[key] <= budget + 1e-9:
            bev.add(key)
    budget_summary: dict[str, float | None] = dict(bev.summary())
    budget_summary["minutes_to_match_engineer_yield"] = minutes_to_match
    budget_summary["minutes_saved_share"] = (
        round(1 - minutes_to_match / budget, 4) if minutes_to_match is not None and budget else None
    )

    observed = None
    if observed_defect_keys:
        eng = set(engineer_keys)
        restricted = [k for k in order if k in eng]
        total = sum(ev.durations[k] for k in restricted)
        cum, found = 0.0, []
        for k in restricted:
            cum += ev.durations[k]
            if k in observed_defect_keys:
                found.append(cum / total)
        observed = round(1 - fmean(found), 4)
    return at_k, budget_summary, observed


def _mean_dicts(dicts: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in dicts[0]:
        vals = [d[key] for d in dicts if d[key] is not None]
        out[key] = round(fmean(vals), 4) if vals else None
    if "minutes_to_match_engineer_yield" in dicts[0]:
        out["match_rate"] = round(
            sum(d["minutes_to_match_engineer_yield"] is not None for d in dicts) / len(dicts), 4
        )
    return out


def evaluate_build(
    data: dict[str, list[Any]],
    build_id: str,
    oracle: Oracle,
    ks: list[int],
    random_repeats: int,
    risk_config: RiskConfig,
    ranking_config: RankingConfig,
    context_cache: dict[str, DecisionContext],
) -> BuildResult:
    visible = visible_data(data, build_id)
    ctx = build_context(build_snapshot(visible, build_id), risk_config)
    context_cache[build_id] = ctx
    model = train_defect_model(data, build_id, ranking_config, context_cache, risk_config)

    rankings: dict[str, list[RankedTest]] = {
        "risk_based": rank_engineering(ctx, ranking_config),
        "hybrid": rank_hybrid(ctx, model, ranking_config),
        "severity_baseline": rank_severity(ctx),
    }
    faults, exposure = oracle.exposure_index(build_id, [c.key for c in ctx.candidates])

    # evaluation-side facts about build B: never passed to rankers
    b_execs = [e for e in data["executions"] if e.build_id == build_id]
    defect_exec_ids = {d.execution_id for d in data["defects"]}
    candidate_keys = {c.key for c in ctx.candidates}
    engineer_keys = [
        (e.test_id, e.variant_id) for e in b_execs if (e.test_id, e.variant_id) in candidate_keys
    ]
    observed_keys = {(e.test_id, e.variant_id) for e in b_execs if e.id in defect_exec_ids}
    eng_ev = _evaluator(ctx, faults, exposure)
    for k in engineer_keys:
        eng_ev.add(k)
    engineer = eng_ev.summary()
    budget = eng_ev.minutes

    at_k, at_budget, observed = {}, {}, {}
    for name, ranked in rankings.items():
        order = [(r.test_id, r.variant_id) for r in ranked]
        at_k[name], at_budget[name], observed[name] = _score_ranking(
            order, ctx, faults, exposure, ks, budget, eng_ev.expected_defects, engineer_keys, observed_keys
        )
    rand = [
        _score_ranking(
            [(r.test_id, r.variant_id) for r in rank_random(ctx, seed)],
            ctx,
            faults,
            exposure,
            ks,
            budget,
            eng_ev.expected_defects,
            engineer_keys,
            observed_keys,
        )
        for seed in range(random_repeats)
    ]
    at_k["random_baseline"] = {str(k): _mean_dicts([r[0][str(k)] for r in rand]) for k in ks}  # type: ignore[misc]
    at_budget["random_baseline"] = _mean_dicts([r[1] for r in rand])
    obs = [r[2] for r in rand if r[2] is not None]
    observed["random_baseline"] = round(fmean(obs), 4) if obs else None

    return BuildResult(
        build_id=build_id,
        candidates=len(ctx.candidates),
        live_faults=len(faults),
        critical_live_faults=sum(1 for f in faults if f.critical),
        engineer_budget_minutes=round(budget, 1),
        engineer=engineer,
        at_k=at_k,
        at_engineer_budget=at_budget,
        observed_replay=observed,
        model=model.info(),
    )


def _aggregate(builds: list[BuildResult], ks: list[int]) -> dict[str, Any]:
    agg: dict[str, Any] = {"at_k": {}, "at_engineer_budget": {}, "observed_replay": {}}
    for s in ALL_STRATEGIES:
        agg["at_k"][s] = {str(k): _mean_dicts([b.at_k[s][str(k)] for b in builds]) for k in ks}
        agg["at_engineer_budget"][s] = _mean_dicts([b.at_engineer_budget[s] for b in builds])
        vals = [v for v in (b.observed_replay[s] for b in builds) if v is not None]
        agg["observed_replay"][s] = round(fmean(vals), 4) if vals else None
    agg["engineer"] = _mean_dicts([b.engineer for b in builds])
    agg["engineer_budget_minutes"] = round(fmean(b.engineer_budget_minutes for b in builds), 1)
    return agg


def _sentence(report: ShadowReport) -> str:
    """Equal-cost comparison first (engineers' own budget), then the K cut-off. All values from the run."""
    agg, k = report.aggregate, "10" if 10 in report.ks else str(report.ks[0])
    b_rb, eng = agg["at_engineer_budget"]["risk_based"], agg["engineer"]
    rb, sev, rnd = (agg["at_k"][s][k] for s in ("risk_based", "severity_baseline", "random_baseline"))
    builds = f"{report.builds[0].build_id}–{report.builds[-1].build_id}"
    text = (
        f"On the synthetic benchmark (seed {report.seed}, builds {builds}), at the historical engineers' own budget "
        f"({agg['engineer_budget_minutes']:,.0f} test-minutes per build) risk-based selection covered "
        f"{b_rb['critical_risk_coverage']:.1%} of critical risk versus {eng['critical_risk_coverage']:.1%} for the "
        f"engineers' actual selection, and recalled {b_rb['critical_defect_recall']:.1%} of critical hidden defects "
        f"versus {eng['critical_defect_recall']:.1%}."
    )
    saved = b_rb.get("minutes_saved_share")
    if saved is not None and b_rb.get("match_rate"):
        direction = "fewer" if saved >= 0 else "more"
        text += (
            f" It matched the engineers' expected defect yield using {abs(saved):.0%} {direction} test-minutes "
            f"(in {b_rb['match_rate']:.0%} of builds)."
        )
    text += (
        f" At K={k} it recalled {rb['critical_defect_recall']:.1%} of critical hidden defects versus "
        f"{sev['critical_defect_recall']:.1%} for severity-first and {rnd['critical_defect_recall']:.1%} for random selection."
    )
    return text


_HIGHER_IS_BETTER = ("critical_risk_coverage", "critical_defect_recall", "defect_recall", "ndcg", "map")


def _findings(report: ShadowReport, margin: float = 0.005) -> list[str]:
    """Every compared metric where another selection beats risk-based ranking. Generated, never curated."""
    agg, out, compared = report.aggregate, [], 0
    for k in report.ks:
        rb = agg["at_k"]["risk_based"][str(k)]
        for other in ALL_STRATEGIES[1:]:
            for m in _HIGHER_IS_BETTER:
                compared += 1
                o, r = agg["at_k"][other][str(k)][m], rb[m]
                if o is not None and r is not None and o > r + margin:
                    out.append(f"{other} beats risk_based on {m} at K={k} ({o:.3f} vs {r:.3f})")
    rb_b = agg["at_engineer_budget"]["risk_based"]
    rivals = {
        "historical_engineer": agg["engineer"],
        **{s: agg["at_engineer_budget"][s] for s in ALL_STRATEGIES[1:]},
    }
    for other, vals in rivals.items():
        for m in (*_HIGHER_IS_BETTER[:3], "expected_defects"):
            compared += 1
            o, r = vals[m], rb_b[m]
            if o is not None and r is not None and o > r + margin:
                out.append(f"{other} beats risk_based on {m} at the engineers' budget ({o:.3f} vs {r:.3f})")
    for other in ALL_STRATEGIES[1:]:
        compared += 1
        o, r = agg["observed_replay"][other], agg["observed_replay"]["risk_based"]
        if o is not None and r is not None and o > r + margin:
            out.append(f"{other} beats risk_based on observed early detection ({o:.3f} vs {r:.3f})")
    return [f"risk_based is best or within {margin} on {compared - len(out)} of {compared} comparisons", *out]


def run_shadow_benchmark(
    dataset_dir: Path,
    ground_truth_path: Path,
    builds: list[str] | None = None,
    ks: tuple[int, ...] = (5, 10, 20, 50),
    random_repeats: int = 20,
    risk_config: RiskConfig | None = None,
    ranking_config: RankingConfig | None = None,
) -> ShadowReport:
    data, manifest = read_dataset(dataset_dir)
    oracle = load_oracle(ground_truth_path, data)
    rcfg, kcfg = risk_config or load_risk_config(), ranking_config or load_ranking_config()
    targets = builds or [b.id for b in sorted(data["builds"], key=lambda b: b.sequence) if b.sequence >= 2]
    cache: dict[str, DecisionContext] = {}
    results = [evaluate_build(data, b, oracle, list(ks), random_repeats, rcfg, kcfg, cache) for b in targets]
    report = ShadowReport(
        seed=manifest.get("seed"),
        generator_version=manifest.get("generator_version", GENERATOR_VERSION),
        risk_config_version=rcfg.version,
        ranking_config_version=kcfg.version,
        ks=list(ks),
        random_repeats=random_repeats,
        builds=results,
    )
    report.aggregate = _aggregate(results, list(ks))
    report.sentence = _sentence(report)
    report.findings = _findings(report)
    return report


def _fmt(v: float | None, pct: bool = True) -> str:
    if v is None:
        return "—"
    return f"{v:.1%}" if pct else f"{v:,.1f}"


def report_markdown(report: ShadowReport) -> str:
    agg = report.aggregate
    lines = [
        "# Shadow Test Planning Benchmark",
        "",
        f"> {report.disclaimer}",
        "",
        f"**Result:** {report.sentence}",
        "",
        "## Findings (generated: where baselines beat risk-based ranking)",
        "",
        *[f"- {f}" for f in report.findings],
        "",
        f"Seed {report.seed} · generator {report.generator_version} · {report.risk_config_version} · "
        f"{report.ranking_config_version} · random baseline averaged over {report.random_repeats} seeds · "
        f"builds {', '.join(b.build_id for b in report.builds)}",
        "",
        "## Ranking cut-offs (mean over builds, counterfactual oracle scoring)",
        "",
    ]
    for k in report.ks:
        lines += [
            f"### K = {k}",
            "",
            "| Strategy | Critical risk coverage | Critical defect recall | Defect recall | Exp. defects | Minutes | NDCG | MAP |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for s in ALL_STRATEGIES:
            m = agg["at_k"][s][str(k)]
            lines.append(
                f"| {s} | {_fmt(m['critical_risk_coverage'])} | {_fmt(m['critical_defect_recall'])} | "
                f"{_fmt(m['defect_recall'])} | {_fmt(m['expected_defects'], False)} | {_fmt(m['minutes'], False)} | "
                f"{m['ndcg']:.3f} | {m['map']:.3f} |"
            )
        lines.append("")
    lines += [
        f"## At the historical engineers' budget ({agg['engineer_budget_minutes']:,.0f} min/build)",
        "",
        "| Selection | Tests | Critical defect recall | Defect recall | Exp. defects | Critical risk coverage | Minutes to match engineer yield | Minutes saved |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    eng = agg["engineer"]
    lines.append(
        f"| historical engineer | {_fmt(eng['tests_selected'], False)} | {_fmt(eng['critical_defect_recall'])} | "
        f"{_fmt(eng['defect_recall'])} | {_fmt(eng['expected_defects'], False)} | {_fmt(eng['critical_risk_coverage'])} | — | — |"
    )
    for s in ALL_STRATEGIES:
        m = agg["at_engineer_budget"][s]
        lines.append(
            f"| {s} | {_fmt(m['tests_selected'], False)} | {_fmt(m['critical_defect_recall'])} | {_fmt(m['defect_recall'])} | "
            f"{_fmt(m['expected_defects'], False)} | {_fmt(m['critical_risk_coverage'])} | "
            f"{_fmt(m['minutes_to_match_engineer_yield'], False)} | {_fmt(m['minutes_saved_share'])} |"
        )
    lines += [
        "",
        "## Observed replay (no oracle)",
        "",
        "Strategies reorder only the tests engineers actually ran; score = 1 − mean fraction of minutes elapsed "
        "before each observed defect is found (0.5 ≈ random order, higher = earlier).",
        "",
        "| Strategy | Early-detection score |",
        "|---|---:|",
    ]
    lines += [
        f"| {s} | {_fmt(agg['observed_replay'][s], False) if agg['observed_replay'][s] is None else f'{agg["observed_replay"][s]:.3f}'} |"
        for s in ALL_STRATEGIES
    ]
    lines += [
        "",
        "## Per build",
        "",
        "| Build | Candidates | Live hidden faults | Critical | Engineer min | Risk-based crit. recall @budget | Engineer crit. recall | Model trained on |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for b in report.builds:
        lines.append(
            f"| {b.build_id} | {b.candidates} | {b.live_faults} | {b.critical_live_faults} | {b.engineer_budget_minutes:,.0f} | "
            f"{_fmt(b.at_engineer_budget['risk_based']['critical_defect_recall'])} | {_fmt(b.engineer['critical_defect_recall'])} | "
            f"{', '.join(b.model['trained_on_builds']) or '—'} ({b.model['n_positive']}/{b.model['n_samples']} pos) |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: ShadowReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "latest.json", out_dir / "latest.md"
    json_path.write_text(json.dumps(asdict(report), indent=1), encoding="utf-8")
    md_path.write_text(report_markdown(report), encoding="utf-8")
    return json_path, md_path
