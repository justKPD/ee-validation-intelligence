# Technical Summary for E/E Validation Researchers and Engineers

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.

**Live demo:** [https://ee-validation-intelligence.vercel.app](https://ee-validation-intelligence.vercel.app) · **API docs:** [https://ee-validation-intelligence-api.up.railway.app/docs](https://ee-validation-intelligence-api.up.railway.app/docs) · **Code:** [https://github.com/justKPD/ee-validation-intelligence](https://github.com/justKPD/ee-validation-intelligence)

## Framing

Inspired by the public description of risk-based E/E validation with agentic AI (risk from impact, occurrence and
detection; coverage derivation; explanation; integration into gate and KPI processes). The prototype studies four gaps
between that architecture and deployment: offline ranking metrics vs defects found, subjective FMEA, linked tests vs
current evidence, and agent reliability. Synthetic programme: 40 fictional ECUs, 150 requirements, 250 tests, 6 builds, 4 variants, 1,821 executions and 124 defects.

## Hidden fault model

Each component draws a latent fragility; per build, faults arise from base rate and change magnitude, propagate along
dependencies and survive undetected into later builds. A test detects a live fault with a hidden, test-level sensitivity.
Observable FMEA occurrence is deliberately mostly noise, and 12% of requirements have no linked test. Ground truth is written
to a separate directory that is never imported into the database or served by the API.

## Benchmark methodology

- **Counterfactual oracle:** each strategy's selection is scored by P(detect) = 1 − Π(1 − sensitivity) over hidden faults live at the build.
- **Equal cost:** strategies are compared at the historical engineers' own minute budget and at K = 5/10/20/50, next to NDCG/MAP.
- **Uncertainty:** bootstrap intervals over builds; tuning only on development seeds [1, 2, 3], comparison on held-out seed 42.
- **Generated reporting:** every sentence and table is generated from runs, including the list of metrics where a baseline wins.

## Leakage prevention

As-of-build snapshots give engines and models no results from the decision build or later. Tests flip every future verdict
and delete future defects and require identical rankings; the ranking package cannot import ground truth or the evaluation package;
the learned model for a build trains only on earlier builds.

## Deterministic vs learned ranking

The engineering score is primary. The learned defect probability (gradient boosting) is calibrated (Brier
0.0542, ECE 0.0386, base rate 5.2%) but ranks
worse (AUROC 0.5993 vs 0.7041); the hybrid adds little.
Engineer-vs-ranker Jaccard at equal budget: 0.2176.

## Agent reliability evaluation and policy boundary

- 25 scenarios × 3 runs (Pass^3): task success, policy compliance, evidence grounding, clarification accuracy, premature action, hallucination.
- Adversarial search: 150 mutants, 0 failures after fixing 28 discovered failure cases, now regression tests.
- Authority boundary: no write API for authoritative data; prohibited tools are registered but denied by a default-deny gate (`POLICY_DENIED`, logged);
  model text cannot introduce ids absent from the facts; human approval is required and recorded in a hash-chained ledger.

## Results

| Result (synthetic benchmark, seed 42) | Value |
|---|---|
| Critical-risk coverage at the engineers' own test budget | 64.6% (engineers 49.3%) |
| Critical hidden-defect recall at that budget | 68.5% (engineers 69.2%) |
| Test-minutes saved while matching the engineers' defect yield | 40.5% (95% CI 20.6%–58.2%, 100.0% of builds) |
| Critical-defect recall in the first 10 tests | 17.5% vs severity-first 7.2%, random 10.4% |
| Defect-ranking AUROC: learned model vs engineering score | 0.5993 vs 0.7041 |
| Agent task success / policy compliance / Pass^3 | 100.0% / 100.0% / 100.0% over 75 runs (before fixes 96.0% / 100.0% / 96.0%) |
| Adversarial search | 150 mutants, 0 failures; 28 found failure cases fixed and kept as regression tests |

## What the results do not show

- **Synthetic data only.** Results describe behaviour against the generator's hidden fault model, not a real E/E programme.
- At equal budget the critical-defect recall difference versus engineers is -0.007 (95% bootstrap CI -0.019 to +0.004, n=5 builds): not distinguishable from zero. The gain is efficiency and risk coverage, not more defects found at the same cost.
- The learned defect model ranks worse than the deterministic engineering score, so engineering risk stays primary.
- risk_based is best or within 0.005 on 68 of 79 comparisons; every metric where a baseline wins is listed in the report.
- The agent's request interpretation is rule-based by design; zero adversarial failures means that mutator set is exhausted, not that the agent is robust in general.
- The public demo has no authentication (reviewer names are self-declared) and a per-client write rate limit.

## Open questions I would like to discuss

- How are risk and coverage reconciled with gate and KPI definitions in practice, and which evidence-freshness rules matter most?
- Would an interventional shadow-mode study (agent recommendations logged beside real selections) be a feasible first step?
- Which agent failure modes (premature action, policy pressure, missing tools) matter most in test-management workflows?

Generated from benchmark results at commit `ed27310` by `scripts/build_brief.py`. Seed 42.
