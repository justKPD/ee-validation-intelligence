# Learning & Calibration Study

> Calibration and tuning study on entirely fictional synthetic data (independent portfolio project).

**Result:** On held-out seed 42, the learned defect model reached AUROC 0.5993 (ECE 0.0386) versus 0.7041 for the engineering score; the configuration selected on development seeds [1, 2, 3] (default_w|cost=0.3|dup=0.2) improved the held-out objective (0.6662 → 0.7465); risk-based minus engineer critical-defect recall at equal budget was -0.007 (95% bootstrap CI -0.019 to +0.004, n=5 builds).

## Findings (generated)

- The learned model ranks observed defects worse than the deterministic engineering score; hybrid weighting should stay conservative.
- The critical-defect-recall difference versus engineers at equal budget is not distinguishable from zero across builds.
- At equal budget the ranker would override 67% of engineer choices (Jaccard 0.22); tests only engineers chose held 12.17 expected hidden defects per build versus 14.79 for tests only the ranker chose.

## Prediction quality on observed executions (builds B003, B004, B005, B006, base rate 5.2%)

| Score | n | Positives | AUROC | Brier | Log loss | ECE |
|---|---:|---:|---:|---:|---:|---:|
| learned_probability | 1255 | 65 | 0.5993 | 0.0542 | 0.2394 | 0.0386 |
| engineering_value | 1255 | 65 | 0.7041 | — | — | — |
| hybrid_value | 1255 | 65 | 0.702 | — | — | — |
| severity | 1255 | 65 | 0.5161 | — | — | — |

### Reliability curve (learned probability)

| Bin | Count | Mean predicted | Observed rate |
|---|---:|---:|---:|
| 0.0–0.1 | 1076 | 0.022 | 0.045 |
| 0.1–0.2 | 109 | 0.135 | 0.083 |
| 0.2–0.3 | 37 | 0.242 | 0.108 |
| 0.3–0.4 | 16 | 0.343 | 0.125 |
| 0.4–0.5 | 4 | 0.440 | 0.000 |
| 0.5–0.6 | 10 | 0.537 | 0.000 |
| 0.6–0.7 | 1 | 0.665 | 1.000 |
| 0.8–0.9 | 2 | 0.814 | 0.000 |

## Tuning on development seeds [1, 2, 3] (never on the held-out seed)

| Configuration | Mean dev objective |
|---|---:|
| **default_w|cost=0.3|dup=0.2** | 0.7564 |
| change_heavy_w|cost=0.3|dup=0.2 | 0.7203 |
| change_heavy_w|cost=0.15|dup=0.2 | 0.6282 |
| default_w|cost=0.15|dup=0.2 | 0.6210 |
| default_w|cost=0.3|dup=0.0 | 0.5519 |
| change_heavy_w|cost=0.3|dup=0.0 | 0.5440 |
| default_w|cost=0.0|dup=0.2 | 0.4684 |
| change_heavy_w|cost=0.0|dup=0.2 | 0.4569 |
| default_w|cost=0.15|dup=0.0 | 0.4225 |
| change_heavy_w|cost=0.15|dup=0.0 | 0.4179 |
| change_heavy_w|cost=0.0|dup=0.0 | 0.2586 |
| default_w|cost=0.0|dup=0.0 | 0.2501 |

## Held-out seed 42: default vs. selected configuration

| Metric | Default | Selected |
|---|---:|---:|
| objective | 0.6662 | 0.7465 |
| critical_defect_recall_at_20 | 0.261 | 0.2332 |
| critical_risk_coverage_at_budget | 0.646 | 0.6508 |
| critical_defect_recall_at_budget | 0.6849 | 0.6901 |
| minutes_saved_share | 0.4052 | 0.5133 |

## Bootstrap uncertainty over decision builds (default configuration)

| Quantity | Mean | 95% CI | n |
|---|---:|---|---:|
| critical_defect_recall_minus_engineer | -0.0070 | -0.0188 … +0.0041 | 5 |
| critical_risk_coverage_minus_engineer | +0.1529 | +0.1320 … +0.1819 | 5 |
| minutes_saved_share | +0.4052 | +0.2064 … +0.5818 | 5 |

## Engineer vs. ranker overrides at equal budget

| Build | Engineer tests | Ranker tests | Jaccard | Override share | Exp. defects engineer-only | Exp. defects ranker-only | Shared |
|---|---:|---:|---:|---:|---:|---:|---:|
| B002 | 288 | 250 | 0.27 | 61% | 11.43 | 14.33 | 13.49 |
| B003 | 304 | 249 | 0.22 | 67% | 5.64 | 13.41 | 13.42 |
| B004 | 317 | 289 | 0.21 | 67% | 19.42 | 17.83 | 18.60 |
| B005 | 317 | 256 | 0.20 | 69% | 4.68 | 4.83 | 3.91 |
| B006 | 317 | 270 | 0.19 | 70% | 19.70 | 23.54 | 23.44 |
