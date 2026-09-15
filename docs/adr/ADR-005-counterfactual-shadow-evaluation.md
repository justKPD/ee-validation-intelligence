# ADR-005 — Counterfactual oracle scoring for shadow test planning

Status: Accepted (2026-09-15)

## Context
Historical records only contain outcomes for tests that engineers chose to run. A recommendation strategy that
selects a test nobody ran cannot be scored from history. Evaluating only inside the executed set would cap every
strategy at the engineers' own choices and hide the question that matters: *would different tests have found more?*

## Decision
- Rankers see only `visible_data(data, B)` (ADR-004). They never read ground truth, and a test scans the
  ranking package source to enforce this.
- The evaluation package loads the synthetic generator's hidden ground truth: live faults per build, fault
  severity and variant scope, and test sensitivity. It scores any selection by **expected detections**
  `1 − Π(1 − sensitivity)`. The scoring is deterministic, with no simulation noise.
- A second, oracle-free **observed replay** reorders only the tests engineers ran and scores how early the
  observed defects appear.
- Strategies are compared at cut-offs K and at the **engineers' own minute budget per build**.
- All numbers, including the summary sentence, are produced by the run and never hard-coded.

## Consequences
The benchmark answers the counterfactual question on synthetic data. That is only possible because the data is
synthetic; with real data the same harness would need interventional studies. This limitation is stated in the report.
