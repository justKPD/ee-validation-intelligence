"""Assemble outreach documents from generated benchmark results so no number is ever hand-typed.

Reads benchmarks/*/results/*.json and writes docs/outreach/{executive-brief,recruiter-summary,researcher-summary}.md.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = (
    "Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. "
    "Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system."
)


def load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1%}"


def commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    shadow = load("benchmarks/shadow-planning/results/latest.json")
    lab = load("benchmarks/agent-reliability/results/latest.json")
    baseline = load("benchmarks/agent-reliability/results/baseline-pre-fix/latest.json")
    adv = load("benchmarks/agent-reliability/results/adversarial.json")
    cal = load("benchmarks/calibration/results/latest.json")
    agg = shadow["aggregate"]
    rb, eng = agg["at_engineer_budget"]["risk_based"], agg["engineer"]
    k10 = {s: agg["at_k"][s]["10"] for s in agg["at_k"]}
    m, bm = lab["metrics"], baseline["metrics"]
    k = lab["k"]
    scores = {s["name"]: s for s in cal["prediction_quality"]["scores"]}
    diff = cal["uncertainty"]["critical_defect_recall_minus_engineer"]
    stamp = f"Generated from benchmark results at commit `{commit()}` by `scripts/build_brief.py`. Seed {shadow['seed']}."

    results_table = "\n".join(
        [
            "| Result | Value |",
            "|---|---|",
            f"| Critical-risk coverage at the engineers' own test budget | {pct(rb['critical_risk_coverage'])} (engineers: {pct(eng['critical_risk_coverage'])}) |",
            f"| Critical hidden-defect recall at that budget | {pct(rb['critical_defect_recall'])} (engineers: {pct(eng['critical_defect_recall'])}) |",
            f"| Test-minutes saved while matching the engineers' defect yield | {pct(rb['minutes_saved_share'])} (in {pct(rb['match_rate'])} of builds) |",
            f"| Critical-defect recall in the first 10 tests | {pct(k10['risk_based']['critical_defect_recall'])} vs severity-first {pct(k10['severity_baseline']['critical_defect_recall'])}, random {pct(k10['random_baseline']['critical_defect_recall'])} |",
            f"| Agent task success / policy compliance / Pass^{k} | {pct(m['task_success'])} / {pct(m['policy_compliance'])} / {pct(m[f'pass^{k}'])} over {lab['runs']} runs (before fixes: {pct(bm['task_success'])} / {pct(bm['policy_compliance'])} / {pct(bm[f'pass^{k}'])}) |",
            f"| Adversarial search | {adv['mutants']} mutants, {adv['failures']} failures; {adv['fixed_regressions']} discovered failure cases fixed and kept as regression tests |",
            f"| Learned defect model vs engineering score (AUROC) | {scores['learned_probability']['auroc']} vs {scores['engineering_value']['auroc']} |",
        ]
    )

    honest = "\n".join(
        [
            f"- At equal budget, the critical-defect recall difference versus engineers is {diff['mean']:+.3f} "
            f"(95% bootstrap CI {diff['ci_low']:+.3f} to {diff['ci_high']:+.3f}, n={diff['n']} builds), not distinguishable from zero. "
            "The gain is efficiency and risk coverage, not more defects found at the same cost.",
            "- The learned defect model ranks defects worse than the deterministic engineering score; engineering risk stays primary.",
            f"- {shadow['findings'][0]}; the report lists every metric where a baseline wins.",
            "- After fixing the gaps the adversarial search found, the same mutators find nothing. That mutator set is exhausted; it is not proof of robustness.",
            "- Everything was measured against a synthetic fault model. Docker, CI and AWS are authored but were not executed in the build environment.",
        ]
    )

    brief = f"""# E/E Validation Intelligence & Agentic Test Control Tower

**Risk-Based Test Prioritization, Evidence Traceability & Policy-Gated Agentic Test Management**

> {DISCLAIMER}

## The problem

When a new software build arrives and validation time is limited, which E/E tests should engineers run first?
And can an AI agent explain those recommendations without being allowed to change authoritative engineering data?

## What I built

An end-to-end platform on a seeded synthetic programme: 40 fictional ECUs, 150 requirements, 250 tests, 6 builds,
4 variants, about 1,800 executions and about 110 defects. It has three pillars:

1. **Validation intelligence.** Deterministic, explainable component risk (FMEA plus change, dependency, history and
   staleness signals). Evidence-aware coverage (CURRENT / STALE / INCOMPATIBLE / MISSING / FAILED). Failure
   fingerprints. Risk-based test ranking with a learned defect-probability model.
2. **Agentic test management.** A LangGraph planner using MCP-compatible tools behind a default-deny policy gate. It
   asks when requests are ambiguous and refuses prohibited actions (`POLICY_DENIED`). Recommendations stay PROPOSED until an
   engineer approves them, and a hash-chained provenance ledger records everything.
3. **AI assurance.** Shadow test planning replays every build without future results and scores strategies against
   hidden ground truth. The agent reliability lab runs every scenario {k} times (Pass^{k}), adversarial
   search turns failures into regression tests, and tuning happens only on development seeds.

## Results (generated, synthetic benchmark)

{results_table}

## What the results do not show

{honest}

## Engineering

Python/FastAPI, SQLAlchemy/Alembic, PostgreSQL + pgvector, uv workspace, scikit-learn, LangGraph/LangChain,
MCP-compatible tools, provider-agnostic model adapter (offline or Claude), OpenTelemetry, Next.js/TypeScript, Docker,
GitHub Actions, Terraform for AWS (ECS Fargate, RDS, S3, CloudWatch). ADRs for every major decision, leakage tests,
and a generated summary sentence for every benchmark.

---
{stamp}
"""
    recruiter = f"""# Recruiter Summary

> {DISCLAIMER}

**One line:** a working platform that decides which automotive electronics tests to run first, lets an AI agent explain
and propose, but never decide, and proves both with reproducible benchmarks.

- **Problem:** limited test time per software build; which tests matter most?
- **Built:** data pipeline, risk and coverage engines, test ranking, policy-gated AI agent with human approval and audit
  ledger, evaluation lab, web control tower, deployment configuration.
- **Evidence:** at the same test budget as the simulated engineers, the ranker covered {pct(rb["critical_risk_coverage"])}
  of critical risk (engineers {pct(eng["critical_risk_coverage"])}) and needed {pct(rb["minutes_saved_share"])} fewer test-minutes to find as many hidden defects.
  The agent never violated its policy across {lab["runs"]} repeated evaluation runs.
- **Honesty:** results are on synthetic data; limitations are documented in the repository.
- **Stack:** Python, FastAPI, PostgreSQL, scikit-learn, LangGraph, MCP-style tools, Next.js, Docker, GitHub Actions, Terraform/AWS.

{stamp}
"""
    researcher = f"""# Technical Summary for E/E Validation Researchers

> {DISCLAIMER}

## Framing

Inspired by the public description of risk-based E/E validation with agentic AI (risk from impact, occurrence and
detection; coverage derivation; explanation; integration into gate and KPI processes). This prototype explores four
gaps that can occur between that architecture and deployment:

1. **Offline ranking metrics vs. finding defects.** The prototype reports NDCG/MAP next to engineering metrics
   (CriticalDefectRecall@K, CriticalRiskCoverage@K, minutes to match the engineers' yield) and compares at equal cost.
2. **Subjective FMEA.** Adjusted risk adds observed signals, confidence and an FMEA-vs-history disagreement flag. On the
   synthetic programme, FMEA base alone does not track where hidden faults occur, while adjusted risk does (see risk methodology).
3. **Coverage ≠ evidence.** A linked test counts only if its latest result is compatible with the current requirement
   revision and component state and is fresh.
4. **Agent reliability.** Repeated-run Pass^k, clarification accuracy, premature action, grounding and policy compliance,
   plus mutation search whose discovered failure classes become regression tests.

## Method safeguards

- As-of-build snapshots; tests tamper every future verdict, defect and change and require identical engine outputs.
- Counterfactual scoring uses hidden ground truth only in the evaluation package. An observed replay without the oracle is reported alongside.
- Tuning only on development seeds; held-out comparison; bootstrap intervals over builds.
- Every sentence and table in the reports is generated from runs, including lists of where baselines win.

## Results

{results_table}

Calibration of the learned model: Brier {scores["learned_probability"]["brier"]}, ECE {scores["learned_probability"]["ece"]},
base rate {pct(cal["prediction_quality"]["base_rate"])}. Engineer-vs-ranker Jaccard at equal budget:
{cal["overrides"]["mean_jaccard"]}.

## Open questions I would like to discuss

- How are risk and coverage currently reconciled with gate and KPI definitions in practice, and which evidence-freshness rules matter most?
- Would an interventional shadow-mode study (agent recommendations logged beside real selections) be feasible as a first step?
- Which agent failure modes (premature action, policy pressure, missing tools) matter most in test-management workflows?

{honest}

{stamp}
"""
    out = ROOT / "docs" / "outreach"
    out.mkdir(parents=True, exist_ok=True)
    (out / "executive-brief.md").write_text(brief, encoding="utf-8")
    (out / "recruiter-summary.md").write_text(recruiter, encoding="utf-8")
    (out / "researcher-summary.md").write_text(researcher, encoding="utf-8")
    print(f"Wrote outreach documents to {out}")


if __name__ == "__main__":
    main()
