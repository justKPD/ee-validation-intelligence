# Technical Summary for E/E Validation Researchers

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.

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

| Result | Value |
|---|---|
| Critical-risk coverage at the engineers' own test budget | 64.6% (engineers: 49.3%) |
| Critical hidden-defect recall at that budget | 68.5% (engineers: 69.2%) |
| Test-minutes saved while matching the engineers' defect yield | 40.5% (in 100.0% of builds) |
| Critical-defect recall in the first 10 tests | 17.5% vs severity-first 7.2%, random 10.4% |
| Agent task success / policy compliance / Pass^3 | 100.0% / 100.0% / 100.0% over 75 runs (before fixes: 96.0% / 100.0% / 96.0%) |
| Adversarial search | 150 mutants, 0 failures; 28 discovered failure cases fixed and kept as regression tests |
| Learned defect model vs engineering score (AUROC) | 0.5993 vs 0.7041 |

Calibration of the learned model: Brier 0.0542, ECE 0.0386,
base rate 5.2%. Engineer-vs-ranker Jaccard at equal budget:
0.2176.

## Open questions I would like to discuss

- How are risk and coverage currently reconciled with gate and KPI definitions in practice, and which evidence-freshness rules matter most?
- Would an interventional shadow-mode study (agent recommendations logged beside real selections) be feasible as a first step?
- Which agent failure modes (premature action, policy pressure, missing tools) matter most in test-management workflows?

- At equal budget, the critical-defect recall difference versus engineers is -0.007 (95% bootstrap CI -0.019 to +0.004, n=5 builds), not distinguishable from zero. The gain is efficiency and risk coverage, not more defects found at the same cost.
- The learned defect model ranks defects worse than the deterministic engineering score; engineering risk stays primary.
- risk_based is best or within 0.005 on 68 of 79 comparisons; the report lists every metric where a baseline wins.
- After fixing the gaps the adversarial search found, the same mutators find nothing. That mutator set is exhausted; it is not proof of robustness.
- Everything was measured against a synthetic fault model. Docker, CI and AWS are authored but were not executed in the build environment.

Generated from benchmark results at commit `ef7f162` by `scripts/build_brief.py`. Seed 42.
