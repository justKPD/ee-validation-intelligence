# Shadow Test Planning Benchmark

> Synthetic benchmark on entirely fictional data from an independent portfolio project. Results must not be interpreted as performance of any real or BMW Group validation process.

**Result:** On the synthetic benchmark (seed 42, builds B002–B006), at the historical engineers' own budget (4,719 test-minutes per build) risk-based selection covered 64.6% of critical risk versus 49.3% for the engineers' actual selection, and recalled 68.5% of critical hidden defects versus 69.2%. It matched the engineers' expected defect yield using 41% fewer test-minutes (in 100% of builds). At K=10 it recalled 17.5% of critical hidden defects versus 7.2% for severity-first and 10.4% for random selection.

## Findings (generated: where baselines beat risk-based ranking)

- risk_based is best or within 0.005 on 68 of 79 comparisons
- severity_baseline beats risk_based on critical_risk_coverage at K=5 (0.018 vs 0.005)
- random_baseline beats risk_based on critical_risk_coverage at K=5 (0.013 vs 0.005)
- severity_baseline beats risk_based on critical_risk_coverage at K=10 (0.053 vs 0.020)
- random_baseline beats risk_based on critical_risk_coverage at K=10 (0.026 vs 0.020)
- severity_baseline beats risk_based on critical_risk_coverage at K=20 (0.088 vs 0.062)
- severity_baseline beats risk_based on critical_risk_coverage at K=50 (0.191 vs 0.158)
- severity_baseline beats risk_based on critical_defect_recall at K=50 (0.426 vs 0.377)
- historical_engineer beats risk_based on critical_defect_recall at the engineers' budget (0.692 vs 0.685)
- hybrid beats risk_based on critical_risk_coverage at the engineers' budget (0.651 vs 0.646)
- hybrid beats risk_based on critical_defect_recall at the engineers' budget (0.691 vs 0.685)
- hybrid beats risk_based on expected_defects at the engineers' budget (16.820 vs 16.761)

Seed 42 · generator 1.1.0 · risk-1.0 · ranking-1.0 · random baseline averaged over 20 seeds · builds B002, B003, B004, B005, B006

## Ranking cut-offs (mean over builds, counterfactual oracle scoring)

### K = 5

| Strategy | Critical risk coverage | Critical defect recall | Defect recall | Exp. defects | Minutes | NDCG | MAP |
|---|---:|---:|---:|---:|---:|---:|---:|
| risk_based | 0.5% | 8.4% | 8.7% | 2.0 | 35.8 | 0.128 | 0.291 |
| hybrid | 0.5% | 3.5% | 3.2% | 0.8 | 56.6 | 0.064 | 0.206 |
| severity_baseline | 1.8% | 4.4% | 7.3% | 1.7 | 65.1 | 0.082 | 0.258 |
| random_baseline | 1.2% | 5.5% | 9.0% | 1.5 | 99.7 | 0.091 | 0.196 |

### K = 10

| Strategy | Critical risk coverage | Critical defect recall | Defect recall | Exp. defects | Minutes | NDCG | MAP |
|---|---:|---:|---:|---:|---:|---:|---:|
| risk_based | 2.0% | 17.5% | 20.6% | 4.0 | 68.5 | 0.169 | 0.354 |
| hybrid | 1.3% | 13.2% | 13.6% | 2.6 | 161.6 | 0.118 | 0.226 |
| severity_baseline | 5.3% | 7.2% | 11.8% | 2.6 | 106.1 | 0.085 | 0.294 |
| random_baseline | 2.6% | 10.4% | 15.3% | 2.8 | 197.6 | 0.096 | 0.154 |

### K = 20

| Strategy | Critical risk coverage | Critical defect recall | Defect recall | Exp. defects | Minutes | NDCG | MAP |
|---|---:|---:|---:|---:|---:|---:|---:|
| risk_based | 6.2% | 26.1% | 35.1% | 6.9 | 147.9 | 0.177 | 0.327 |
| hybrid | 4.1% | 21.5% | 27.0% | 4.7 | 331.2 | 0.138 | 0.192 |
| severity_baseline | 8.8% | 11.1% | 15.1% | 3.4 | 438.3 | 0.077 | 0.203 |
| random_baseline | 4.9% | 18.2% | 27.2% | 5.0 | 387.6 | 0.108 | 0.128 |

### K = 50

| Strategy | Critical risk coverage | Critical defect recall | Defect recall | Exp. defects | Minutes | NDCG | MAP |
|---|---:|---:|---:|---:|---:|---:|---:|
| risk_based | 15.8% | 37.6% | 51.0% | 9.1 | 567.2 | 0.191 | 0.234 |
| hybrid | 13.3% | 35.2% | 50.8% | 9.1 | 746.0 | 0.180 | 0.215 |
| severity_baseline | 19.1% | 42.6% | 45.0% | 9.6 | 993.0 | 0.157 | 0.196 |
| random_baseline | 11.4% | 37.5% | 50.4% | 9.5 | 974.5 | 0.142 | 0.114 |

## At the historical engineers' budget (4,719 min/build)

| Selection | Tests | Critical defect recall | Defect recall | Exp. defects | Critical risk coverage | Minutes to match engineer yield | Minutes saved |
|---|---:|---:|---:|---:|---:|---:|---:|
| historical engineer | 308.6 | 69.2% | 82.4% | 16.1 | 49.3% | — | — |
| risk_based | 262.8 | 68.5% | 85.9% | 16.8 | 64.6% | 2,810.7 | 40.5% |
| hybrid | 272.4 | 69.1% | 86.0% | 16.8 | 65.1% | 2,940.2 | 37.0% |
| severity_baseline | 249.4 | 67.4% | 76.4% | 15.1 | 55.7% | 6,811.2 | -43.2% |
| random_baseline | 244.2 | 67.1% | 82.5% | 16.1 | 41.9% | 4,774.8 | -1.0% |

## Observed replay (no oracle)

Strategies reorder only the tests engineers actually ran; score = 1 − mean fraction of minutes elapsed before each observed defect is found (0.5 ≈ random order, higher = earlier).

| Strategy | Early-detection score |
|---|---:|
| risk_based | 0.716 |
| hybrid | 0.701 |
| severity_baseline | 0.431 |
| random_baseline | 0.503 |

## Per build

| Build | Candidates | Live hidden faults | Critical | Engineer min | Risk-based crit. recall @budget | Engineer crit. recall | Model trained on |
|---|---:|---:|---:|---:|---:|---:|---|
| B002 | 525 | 18 | 9 | 4,294 | 87.1% | 88.9% | B001 (44/278 pos) |
| B003 | 553 | 18 | 11 | 4,681 | 80.3% | 79.1% | B001, B002 (59/566 pos) |
| B004 | 577 | 24 | 15 | 4,819 | 85.5% | 85.8% | B001, B002, B003 (73/870 pos) |
| B005 | 577 | 6 | 1 | 4,851 | 0.0% | 0.0% | B001, B002, B003, B004 (94/1187 pos) |
| B006 | 577 | 30 | 13 | 4,950 | 89.6% | 92.2% | B001, B002, B003, B004, B005 (98/1504 pos) |
