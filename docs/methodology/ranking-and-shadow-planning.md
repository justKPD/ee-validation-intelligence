# Test Ranking & Shadow Test Planning Methodology (Phases 3–4)

Current results: [`benchmarks/shadow-planning/results/latest.md`](../../benchmarks/shadow-planning/results/latest.md).
All numbers there are produced by `uv run ee-shadow`; nothing in this document or the report is hand-entered.

## Candidates and features

A candidate is an applicable (test case, vehicle variant) pair. Features are computed as of the decision build
from the Phase 2 engines:

| Feature | Source |
|---|---|
| risk_exposure | max requirement risk over the test's requirements |
| uncovered | share of the test's (requirement, variant) evidence pairs that are not CURRENT |
| change_relevance | max `recent_change` risk factor of the test's components |
| historical_failure | smoothed per-test defect rate: `min(1, ((defects + 0.5)/(runs + 5)) / 0.3)` |
| dependency | max `dependency` risk factor of the test's components |
| stale_evidence | builds since this (test, variant) last ran, normalised; 1 if never run |
| critical, failed_evidence, open_failure_family, max_severity, duration | additional learned-model inputs |

## Strategies

| Strategy | Definition |
|---|---|
| `risk_based` | greedy: `Σ w·feature − 0.15·duration/max_duration − 0.20·(share of pairs already covered)` ([`config/ranking.toml`](../../config/ranking.toml)) |
| `hybrid` | same greedy with value `0.65·engineering + 0.35·P(defect)`; the model is scikit-learn `HistGradientBoostingClassifier` trained only on executions from builds before the decision build |
| `severity_baseline` | static: highest linked requirement severity first |
| `random_baseline` | seeded shuffle, metrics averaged over 20 seeds |
| historical engineer | the (test, variant) pairs actually executed in the build; compared at its own minute budget |

## Leakage prevention

- Rankers receive a `DecisionContext` built from `visible_data(data, B)`: no results of B or later ([ADR-004](../adr/ADR-004-as-of-snapshots.md)).
- The learned model for B is trained from `visible_data(data, B)` only; the report lists the training builds.
- Tests assert that rankings are unchanged when every future verdict is flipped and future defects are removed,
  and that the ranking package source never references ground truth or the evaluation package.

## Scoring ([ADR-005](../adr/ADR-005-counterfactual-shadow-evaluation.md))

**Counterfactual oracle.** Hidden faults live at the start of B are scored with `P(detect f) = 1 − Π(1 − sensitivity)`
over selected pairs touching the fault's component on an in-scope variant.

| Metric | Meaning |
|---|---|
| CriticalDefectRecall | expected share of live hidden faults with severity ≥ 4 that are detected |
| DefectRecall / expected defects | same for all live hidden faults |
| CriticalRiskCoverage | share of severity×impact weight of critical (requirement, variant) pairs lacking CURRENT evidence that the selection covers |
| CoverageGain | share of all non-CURRENT (requirement, variant) pairs covered |
| …PerHour | the above divided by selected test-hours |
| NDCG@K / MAP@K | graded relevance = Σ sensitivity × severity of detectable live faults; binary relevance for MAP |
| Minutes to match engineer yield | test-minutes a strategy needs to reach the engineers' expected defect yield for that build |

Comparisons at **K** mix selections of very different cost. The comparison at the **engineers' own minute budget**
(budget fill: skip tests that no longer fit) is the equal-cost comparison and is used first in the summary sentence.

**Observed replay (no oracle).** Strategies reorder only the tests engineers ran in B. The score is
`1 − mean(fraction of minutes elapsed when each observed defect is found)`: 0.5 is about random, higher is earlier.

## Reading the result honestly

The report includes a generated **Findings** list of every metric where a baseline beats `risk_based`. On the
committed run, for example, the severity-first baseline achieves higher per-K critical-risk coverage because the
cost penalty makes the risk ranker prefer shorter tests, and the hybrid model does not improve on pure
engineering ranking. These are reported as-is and are inputs for Phase 11 (calibration), where weights will be
tuned on **separate development seeds** and evaluated on held-out seeds, never on the reported seed.

## Limitations

- The oracle exists only because the data is synthetic; its fault process is described in
  [synthetic-data.md](synthetic-data.md). Results measure performance against this generative model only.
- Nominal test durations are used for all strategies, including the engineers' selection.
- Five decision builds per seed; per-build variance is visible in the report (for example, a build with a single critical fault).
