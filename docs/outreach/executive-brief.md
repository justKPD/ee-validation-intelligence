# E/E Validation Intelligence & Agentic Test Control Tower

**Risk-Based Test Prioritization, Evidence Traceability & Policy-Gated Agentic Test Management**

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.

## The problem

When a new software build arrives and validation time is limited, which E/E tests should engineers run first?
And can an AI agent explain those recommendations without being allowed to change authoritative engineering data?

## What I built

An end-to-end platform on a seeded synthetic programme: 40 fictional ECUs, 150 requirements,
250 tests, 6 builds, 4 variants, 1,821 executions and 124 defects. It has three pillars:

1. **Validation intelligence.** Deterministic, explainable component risk (FMEA plus change, dependency, history and
   staleness signals). Evidence-aware coverage (CURRENT / STALE / INCOMPATIBLE / MISSING / FAILED). Failure
   fingerprints. Risk-based test ranking with a learned defect-probability model.
2. **Agentic test management.** A LangGraph planner using MCP-compatible tools behind a default-deny policy gate. It
   asks when requests are ambiguous and refuses prohibited actions (`POLICY_DENIED`). Recommendations stay PROPOSED until an
   engineer approves them, and a hash-chained provenance ledger records everything.
3. **AI assurance.** Shadow test planning replays every build without future results and scores strategies against
   hidden ground truth. The agent reliability lab runs every scenario 3 times (Pass^3), adversarial
   search turns failures into regression tests, and tuning happens only on development seeds.

## Results (generated, synthetic benchmark)

| Result | Value |
|---|---|
| Critical-risk coverage at the engineers' own test budget | 64.6% (engineers: 49.3%) |
| Critical hidden-defect recall at that budget | 68.5% (engineers: 69.2%) |
| Test-minutes saved while matching the engineers' defect yield | 40.5% (in 100.0% of builds) |
| Critical-defect recall in the first 10 tests | 17.5% vs severity-first 7.2%, random 10.4% |
| Agent task success / policy compliance / Pass^3 | 100.0% / 100.0% / 100.0% over 75 runs (before fixes: 96.0% / 100.0% / 96.0%) |
| Adversarial search | 150 mutants, 0 failures; 28 discovered failure cases fixed and kept as regression tests |
| Learned defect model vs engineering score (AUROC) | 0.5993 vs 0.7041 |

## What the results do not show

- At equal budget, the critical-defect recall difference versus engineers is -0.007 (95% bootstrap CI -0.019 to +0.004, n=5 builds), not distinguishable from zero. The gain is efficiency and risk coverage, not more defects found at the same cost.
- The learned defect model ranks defects worse than the deterministic engineering score; engineering risk stays primary.
- risk_based is best or within 0.005 on 68 of 79 comparisons; the report lists every metric where a baseline wins.
- After fixing the gaps the adversarial search found, the same mutators find nothing. That mutator set is exhausted; it is not proof of robustness.
- Everything was measured against a synthetic fault model. The Dockerized API/web/database stack was validated locally (PostgreSQL 16.15, pgvector 0.8.6); GitHub Actions CI is green on GitHub, including Terraform fmt/validate; the AWS deployment is authored but not yet applied.

## Engineering

Python/FastAPI, SQLAlchemy/Alembic, PostgreSQL + pgvector, uv workspace, scikit-learn, LangGraph/LangChain,
MCP-compatible tools, provider-agnostic model adapter (offline or Claude), OpenTelemetry, Next.js/TypeScript, Docker,
GitHub Actions, Terraform for AWS (ECS Fargate, RDS, S3, CloudWatch). ADRs for every major decision, leakage tests,
and a generated summary sentence for every benchmark.

---
Generated from benchmark results at commit `53a654e` by `scripts/build_brief.py`. Seed 42.
