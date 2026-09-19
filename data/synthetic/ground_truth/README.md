# ⚠️ Hidden ground truth — the oracle

This folder is the **answer key** for the synthetic programme. It is published here **only so reviewers can inspect
how the benchmark is graded** — in the running system it is treated as hidden:

- The engines, the risk/ranking models, the agent, the database and the API **never read this folder**.
- Only the evaluation package reads it, and only **after** a test selection has already been made, to score that
  selection against faults the engines could not see (leakage-safe shadow planning, see
  [`docs/adr/ADR-005-counterfactual-shadow-evaluation.md`](../../../docs/adr/ADR-005-counterfactual-shadow-evaluation.md)).

`ground_truth.json`:

| Key | Meaning |
|---|---|
| `faults` | every injected fault: component, injected build, `live_builds`, `variant_scope`, `severity`, whether it was `detected` and by which execution |
| `latent_fragility` | each component's true failure-proneness (0–1) |
| `test_sensitivity` | each test's true probability of detecting a fault it touches (0–1) |

Reproducible from seed 42. See [`data/README.md`](../../README.md).
