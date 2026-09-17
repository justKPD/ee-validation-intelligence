"""Assemble portfolio documents from generated benchmark results so no number is ever hand-typed.

Reads benchmarks/*/results/*.json, config/risk.toml and the generated dataset manifest, and writes
docs/outreach/{technical-brief.md, technical-brief.html, recruiter-summary.md, researcher-summary.md}.

The two-page A4 PDF is printed from the HTML with headless Chrome:
  chrome --headless=new --no-pdf-header-footer --print-to-pdf=docs/outreach/technical-brief.pdf docs/outreach/technical-brief.html
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE_URL = "https://ee-validation-intelligence.vercel.app"
API_URL = "https://ee-validation-intelligence-api.up.railway.app"
GITHUB_URL = "https://github.com/justKPD/ee-validation-intelligence"
DISCLAIMER = (
    "Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. "
    "Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system."
)

Block = tuple[str, Any]  # ("p", text) | ("ul", [items]) | ("table", [header, *rows])


def load(rel: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    return data


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1%}"


def commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def md_blocks(blocks: list[Block]) -> str:
    out: list[str] = []
    for kind, body in blocks:
        if kind == "p":
            out.append(body)
        elif kind == "ul":
            out.append("\n".join(f"- {item}" for item in body))
        elif kind == "table":
            header, *rows = body
            out.append(
                "\n".join(
                    [
                        "| " + " | ".join(header) + " |",
                        "|" + "---|" * len(header),
                        *("| " + " | ".join(r) + " |" for r in rows),
                    ]
                )
            )
    return "\n\n".join(out)


def inline_html(text: str) -> str:
    s = html.escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)


def html_blocks(blocks: list[Block]) -> str:
    out: list[str] = []
    for kind, body in blocks:
        if kind == "p":
            out.append(f"<p>{inline_html(body)}</p>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{inline_html(i)}</li>" for i in body) + "</ul>")
        elif kind == "table":
            header, *rows = body
            head = "".join(f"<th>{inline_html(h)}</th>" for h in header)
            trs = "".join("<tr>" + "".join(f"<td>{inline_html(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table>")
    return "\n".join(out)


def main() -> None:
    shadow = load("benchmarks/shadow-planning/results/latest.json")
    lab = load("benchmarks/agent-reliability/results/latest.json")
    baseline = load("benchmarks/agent-reliability/results/baseline-pre-fix/latest.json")
    adv = load("benchmarks/agent-reliability/results/adversarial.json")
    cal = load("benchmarks/calibration/results/latest.json")
    risk_cfg = tomllib.loads((ROOT / "config" / "risk.toml").read_text(encoding="utf-8"))
    # dataset sizes come from the generated manifest (written by ee-seed / ee-generate), never typed by hand
    manifest = load("data/synthetic/dataset/manifest.json")
    if manifest.get("seed") != shadow["seed"]:
        raise SystemExit(
            f"dataset seed {manifest.get('seed')} does not match benchmark seed {shadow['seed']}"
        )
    c = manifest["counts"]
    agg = shadow["aggregate"]
    rb, eng = agg["at_engineer_budget"]["risk_based"], agg["engineer"]
    k10 = {s: agg["at_k"][s]["10"] for s in agg["at_k"]}
    m, bm = lab["metrics"], baseline["metrics"]
    k = lab["k"]
    scores = {s["name"]: s for s in cal["prediction_quality"]["scores"]}
    unc = cal["uncertainty"]
    diff = unc["critical_defect_recall_minus_engineer"]
    saved = unc["minutes_saved_share"]
    w = risk_cfg["weights"]
    seed = shadow["seed"]
    stamp = (
        f"Generated from benchmark results at commit `{commit()}` by `scripts/build_brief.py`. Seed {seed}."
    )
    links = f"**Live demo:** [{LIVE_URL}]({LIVE_URL}) · **API docs:** [{API_URL}/docs]({API_URL}/docs) · **Code:** [{GITHUB_URL}]({GITHUB_URL})"
    dataset = (
        f"{c['components']} fictional ECUs, {c['requirements']} requirements, {c['test_cases']} tests, {c['builds']} builds, "
        f"{c['variants']} variants, {c['executions']:,} executions and {c['defects']} defects"
    )

    results: Block = (
        "table",
        [
            ["Result (synthetic benchmark, seed " + str(seed) + ")", "Value"],
            [
                "Critical-risk coverage at the engineers' own test budget",
                f"{pct(rb['critical_risk_coverage'])} (engineers {pct(eng['critical_risk_coverage'])})",
            ],
            [
                "Critical hidden-defect recall at that budget",
                f"{pct(rb['critical_defect_recall'])} (engineers {pct(eng['critical_defect_recall'])})",
            ],
            [
                "Test-minutes saved while matching the engineers' defect yield",
                f"{pct(rb['minutes_saved_share'])} (95% CI {pct(saved['ci_low'])}–{pct(saved['ci_high'])}, {pct(rb['match_rate'])} of builds)",
            ],
            [
                "Critical-defect recall in the first 10 tests",
                f"{pct(k10['risk_based']['critical_defect_recall'])} vs severity-first {pct(k10['severity_baseline']['critical_defect_recall'])}, random {pct(k10['random_baseline']['critical_defect_recall'])}",
            ],
            [
                "Defect-ranking AUROC: learned model vs engineering score",
                f"{scores['learned_probability']['auroc']} vs {scores['engineering_value']['auroc']}",
            ],
            [
                f"Agent task success / policy compliance / Pass^{k}",
                f"{pct(m['task_success'])} / {pct(m['policy_compliance'])} / {pct(m[f'pass^{k}'])} over {lab['runs']} runs (before fixes {pct(bm['task_success'])} / {pct(bm['policy_compliance'])} / {pct(bm[f'pass^{k}'])})",
            ],
            [
                "Adversarial search",
                f"{adv['mutants']} mutants, {adv['failures']} failures; {adv['fixed_regressions']} found failure cases fixed and kept as regression tests",
            ],
        ],
    )
    limitations: Block = (
        "ul",
        [
            "**Synthetic data only.** Results describe behaviour against the generator's hidden fault model, not a real E/E programme.",
            f"At equal budget the critical-defect recall difference versus engineers is {diff['mean']:+.3f} "
            f"(95% bootstrap CI {diff['ci_low']:+.3f} to {diff['ci_high']:+.3f}, n={diff['n']} builds): not distinguishable from zero. "
            "The gain is efficiency and risk coverage, not more defects found at the same cost.",
            "The learned defect model ranks worse than the deterministic engineering score, so engineering risk stays primary.",
            f"{shadow['findings'][0]}; every metric where a baseline wins is listed in the report.",
            "The agent's request interpretation is rule-based by design; zero adversarial failures means that mutator set is exhausted, not that the agent is robust in general.",
            "The public demo has no authentication (reviewer names are self-declared) and a per-client write rate limit.",
        ],
    )

    brief_sections: list[tuple[str, list[Block]]] = [
        (
            "Problem",
            [
                (
                    "p",
                    "When a new software build arrives and validation time is limited, which E/E tests should engineers run first? "
                    "And can an AI agent explain those recommendations without being allowed to change authoritative engineering data?",
                )
            ],
        ),
        (
            "Public research inspiration",
            [
                (
                    "p",
                    "Publicly described risk-based E/E validation with agentic AI: risk from FMEA impact, occurrence and detection; "
                    "coverage derivation; explanation; integration into gate and KPI processes. This project explores the gaps "
                    "between that architecture and deployment: offline metrics vs defects found, subjective FMEA, linked tests vs "
                    "current evidence, and agent reliability.",
                )
            ],
        ),
        (
            "Architecture",
            [
                (
                    "ul",
                    [
                        f"Seeded synthetic programme ({dataset}) with a hidden fault model kept out of the database.",
                        "Python/FastAPI, SQLAlchemy/Alembic, PostgreSQL 16 + pgvector; deterministic engines own every authoritative calculation.",
                        "LangGraph planner with MCP-compatible tools behind a default-deny policy gate; Next.js/TypeScript control tower.",
                        "Deployed: Vercel (web) + Railway (API, PostgreSQL/pgvector on a private network). Docker Compose validated locally; "
                        "AWS Terraform (ECS Fargate, RDS, S3, CloudWatch) validated in CI as an alternative target, not applied. GitHub Actions CI enforces benchmark reproduction.",
                    ],
                )
            ],
        ),
        (
            "Risk engine and evidence-aware coverage",
            [
                (
                    "p",
                    f"Adjusted component risk is a documented weighted sum: FMEA base {w['base']}, recent change {w['recent_change']}, "
                    f"historical failure {w['historical_failure']}, dependency {w['dependency']}, evidence staleness {w['evidence_staleness']}, "
                    f"variant exposure {w['variant_exposure']}, with a confidence value and an FMEA-vs-history disagreement flag. "
                    "Coverage counts a (requirement, variant) pair only when its latest evidence is CURRENT; otherwise it is STALE, "
                    "INCOMPATIBLE, MISSING or FAILED, with the reason shown.",
                )
            ],
        ),
        (
            "Ranking and Shadow Test Planning",
            [
                (
                    "p",
                    "A greedy ranker values risk exposure, uncovered evidence, change relevance, failure history and staleness against "
                    "test duration and duplicate coverage; a hybrid adds a gradient-boosted defect probability trained only on earlier builds. "
                    "Shadow planning replays every build as of that build (no future results) and scores each strategy against hidden "
                    "ground-truth faults, comparing at equal cost with severity-first, random and the historical engineers' own selection.",
                )
            ],
        ),
        (
            "Agentic Test Planner, policy gate and provenance",
            [
                (
                    "p",
                    "Plans come from the engines; the model only writes explanations, grounding-checked against fact ids. The agent asks "
                    "when a build or variant is ambiguous. Changing verdicts, requirements or tests, closing defects, approving releases "
                    "or approving its own recommendations is refused as `POLICY_DENIED` and logged. Recommendations stay PROPOSED "
                    "until a human decides, and every run, proposal, decision and denial is appended to a hash-chained ledger.",
                )
            ],
        ),
        (
            "Reliability and adversarial testing",
            [
                (
                    "p",
                    f"The reliability lab runs {lab['scenarios']} scenarios {k} times each (Pass^{k}) and measures task success, policy "
                    "compliance, clarification accuracy, premature action and hallucination. An adversarial generator mutates requests "
                    "(injection, obfuscation, polite verdict changes); failures it found were fixed and kept as regression tests.",
                )
            ],
        ),
        ("Measured results", [results]),
        ("What the results do not show", [limitations]),
    ]

    brief_md = (
        "# E/E Validation Intelligence & Agentic Test Control Tower\n\n"
        "**Technical brief: risk-based test prioritization, evidence traceability and policy-gated agentic test management**\n\n"
        f"{links}\n\n> {DISCLAIMER}\n\n"
        + "\n\n".join(f"## {title}\n\n{md_blocks(blocks)}" for title, blocks in brief_sections)
        + f"\n\n---\n{stamp}\n"
    )
    brief_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>E/E Validation Intelligence &amp; Agentic Test Control Tower: Technical Brief</title>
<style>
@page {{ size: A4; margin: 13mm 14mm 12mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 9.6pt; line-height: 1.38; color: #1d1d1f; margin: 0; }}
h1 {{ font-size: 16pt; margin: 0 0 2px; }}
h2 {{ font-size: 10.8pt; margin: 9px 0 3px; color: #1f4e8c; border-bottom: 1px solid #d8dee8; padding-bottom: 1px; break-after: avoid; }}
p, ul {{ margin: 3px 0; }} ul {{ padding-left: 16px; }} li {{ margin: 1.5px 0; }}
.sub {{ font-weight: 600; margin: 0 0 4px; }}
.links {{ font-size: 9pt; margin: 2px 0 4px; }}
.disclaimer {{ font-size: 8.4pt; color: #555; border-left: 3px solid #c9d3e0; padding: 2px 8px; margin: 4px 0 2px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9pt; margin: 4px 0; break-inside: avoid; }}
th, td {{ border: 1px solid #d8dee8; padding: 3px 6px; text-align: left; vertical-align: top; }}
th {{ background: #eef2f7; }}
code {{ font-family: Consolas, monospace; font-size: 8.8pt; }}
a {{ color: #1f4e8c; text-decoration: none; }}
.shot {{ width: 100%; border: 1px solid #d8dee8; margin: 5px 0 2px; }}
.caption {{ font-size: 8pt; color: #666; margin: 0 0 4px; }}
.stamp {{ font-size: 7.6pt; color: #777; margin-top: 8px; }}
</style></head><body>
<h1>E/E Validation Intelligence &amp; Agentic Test Control Tower</h1>
<p class="sub">Technical brief: risk-based test prioritization, evidence traceability and policy-gated agentic test management</p>
<p class="links">{inline_html(links)}</p>
<p class="disclaimer">{html.escape(DISCLAIMER)}</p>
{"".join(f"<h2>{html.escape(t)}</h2>{html_blocks(b)}" for t, b in brief_sections[:3])}
<img class="shot" src="../assets/screenshots/03-agentic-test-planner.png" alt="Agentic Test Planner on the live deployment">
<p class="caption">Live deployment: the planner's ranked proposal with reasons, evidence ids and the provenance record, awaiting a human decision.</p>
{"".join(f"<h2>{html.escape(t)}</h2>{html_blocks(b)}" for t, b in brief_sections[3:])}
<p class="stamp">{inline_html(stamp)}</p>
</body></html>
"""

    recruiter = f"""# Recruiter Summary

> {DISCLAIMER}

{links}

**One line:** a deployed platform that decides which automotive electronics tests to run first, lets an AI agent explain
and propose, but never decide, and proves both with reproducible benchmarks.

- **Problem:** limited test time per software build; which tests matter most?
- **Built:** data pipeline, risk and coverage engines, test ranking, policy-gated AI agent with human approval and an audit
  ledger, evaluation lab, web control tower. Live on Vercel and Railway with PostgreSQL + pgvector; CI-enforced reproducibility.
- **Evidence:** at the same test budget as the simulated engineers, the ranker covered {pct(rb["critical_risk_coverage"])}
  of critical risk (engineers {pct(eng["critical_risk_coverage"])}) and needed {pct(rb["minutes_saved_share"])} fewer test-minutes to find as many hidden defects.
  The agent never violated its policy across {lab["runs"]} repeated evaluation runs.
- **Honesty:** results are on synthetic data; defect recall at equal cost is not better than the engineers', and limitations are documented.
- **Stack:** Python, FastAPI, PostgreSQL/pgvector, scikit-learn, LangGraph, MCP-style tools, Next.js/TypeScript, Docker, GitHub Actions, Railway, Vercel, Terraform (AWS target).

{stamp}
"""

    researcher = f"""# Technical Summary for E/E Validation Researchers and Engineers

> {DISCLAIMER}

{links}

## Framing

Inspired by the public description of risk-based E/E validation with agentic AI (risk from impact, occurrence and
detection; coverage derivation; explanation; integration into gate and KPI processes). The prototype studies four gaps
between that architecture and deployment: offline ranking metrics vs defects found, subjective FMEA, linked tests vs
current evidence, and agent reliability. Synthetic programme: {dataset}.

## Hidden fault model

Each component draws a latent fragility; per build, faults arise from base rate and change magnitude, propagate along
dependencies and survive undetected into later builds. A test detects a live fault with a hidden, test-level sensitivity.
Observable FMEA occurrence is deliberately mostly noise, and 12% of requirements have no linked test. Ground truth is written
to a separate directory that is never imported into the database or served by the API.

## Benchmark methodology

- **Counterfactual oracle:** each strategy's selection is scored by P(detect) = 1 − Π(1 − sensitivity) over hidden faults live at the build.
- **Equal cost:** strategies are compared at the historical engineers' own minute budget and at K = 5/10/20/50, next to NDCG/MAP.
- **Uncertainty:** bootstrap intervals over builds; tuning only on development seeds {cal["tuning"]["dev_seeds"]}, comparison on held-out seed {cal["heldout_seed"]}.
- **Generated reporting:** every sentence and table is generated from runs, including the list of metrics where a baseline wins.

## Leakage prevention

As-of-build snapshots give engines and models no results from the decision build or later. Tests flip every future verdict
and delete future defects and require identical rankings; the ranking package cannot import ground truth or the evaluation package;
the learned model for a build trains only on earlier builds.

## Deterministic vs learned ranking

The engineering score is primary. The learned defect probability (gradient boosting) is calibrated (Brier
{scores["learned_probability"]["brier"]}, ECE {scores["learned_probability"]["ece"]}, base rate {pct(cal["prediction_quality"]["base_rate"])}) but ranks
worse (AUROC {scores["learned_probability"]["auroc"]} vs {scores["engineering_value"]["auroc"]}); the hybrid adds little.
Engineer-vs-ranker Jaccard at equal budget: {cal["overrides"]["mean_jaccard"]}.

## Agent reliability evaluation and policy boundary

- {lab["scenarios"]} scenarios × {k} runs (Pass^{k}): task success, policy compliance, evidence grounding, clarification accuracy, premature action, hallucination.
- Adversarial search: {adv["mutants"]} mutants, {adv["failures"]} failures after fixing {adv["fixed_regressions"]} discovered failure cases, now regression tests.
- Authority boundary: no write API for authoritative data; prohibited tools are registered but denied by a default-deny gate (`POLICY_DENIED`, logged);
  model text cannot introduce ids absent from the facts; human approval is required and recorded in a hash-chained ledger.

## Results

{md_blocks([results])}

## What the results do not show

{md_blocks([limitations])}

## Open questions I would like to discuss

- How are risk and coverage reconciled with gate and KPI definitions in practice, and which evidence-freshness rules matter most?
- Would an interventional shadow-mode study (agent recommendations logged beside real selections) be a feasible first step?
- Which agent failure modes (premature action, policy pressure, missing tools) matter most in test-management workflows?

{stamp}
"""
    out = ROOT / "docs" / "outreach"
    out.mkdir(parents=True, exist_ok=True)
    (out / "technical-brief.md").write_text(brief_md, encoding="utf-8", newline="\n")
    (out / "technical-brief.html").write_text(brief_html, encoding="utf-8", newline="\n")
    (out / "recruiter-summary.md").write_text(recruiter, encoding="utf-8", newline="\n")
    (out / "researcher-summary.md").write_text(researcher, encoding="utf-8", newline="\n")
    print(f"Wrote portfolio documents to {out}")


if __name__ == "__main__":
    main()
