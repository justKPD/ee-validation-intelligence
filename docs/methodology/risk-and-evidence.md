# Risk, Evidence & Failure Methodology (Phase 2)

All calculations are deterministic Python over an as-of-build snapshot ([ADR-004](../adr/ADR-004-as-of-snapshots.md)).
No LLM computes or modifies any of these values.

## Component risk

`AdjustedRisk = Σ weight_f · factor_f`. Weights live in [`config/risk.toml`](../../config/risk.toml) and must sum to 1.

| Factor | Definition | Default weight |
|---|---|---:|
| base | mean(FMEA impact × occurrence × detectability) / 1000 over the component's requirements | 0.35 |
| recent_change | max change magnitude in the build; a revised linked requirement counts 0.6 | 0.20 |
| historical_failure | `min(1, ((defects + 1) / (executions + 10)) / 0.3)` (Beta(1, 9) prior) | 0.15 |
| dependency | 0.7 × max recent_change of upstream components | 0.10 |
| evidence_staleness | share of the component's (test, variant) pairs not run on the previous build | 0.10 |
| variant_exposure | share of variants the component's tests apply to | 0.10 |

Every response carries factors, weighted contributions, normalized impact/occurrence/detectability,
`confidence = executions / (executions + 20)`, and flags:

- `LOW_EVIDENCE`: confidence < 0.3
- `FMEA_HISTORY_DISAGREEMENT`: confidence ≥ 0.5 and |FMEA occurrence − observed failure signal| > 0.45.
  This flags cases where expert FMEA judgement and field evidence disagree.

## Requirement risk

`0.4 · FMEA base + 0.4 · max(linked component risk) + 0.2 · [revised in this build]`.
A requirement is **critical** if severity ≥ 4 or FMEA impact ≥ 8.

## Evidence status

Each (requirement, applicable variant) pair gets the dominant status over its linked tests' latest
non-blocked executions: `FAILED > CURRENT > STALE > INCOMPATIBLE > MISSING`.

| Status | Rule |
|---|---|
| MISSING | no linked test, or no execution on this variant |
| FAILED | latest execution failed |
| INCOMPATIBLE | requirement revised after the evidence was produced |
| STALE | a linked component changed after the evidence build, or age > 35 days |
| CURRENT | passing, same requirement revision, no later component change, fresh |

`Evidence coverage = CURRENT pairs / all pairs`, reported next to structural coverage (requirements with ≥ 1 test).

## Diagnostic: does risk track hidden truth?

This offline diagnostic reads the generator's hidden ground truth, which no engine can access. For each build
it computes the Spearman rank correlation between each component's risk score and the number of faults
actually injected into that component in that build (seed 42, 40 components):

| Build | Injected faults | Adjusted risk ρ | FMEA base only ρ |
|---|---:|---:|---:|
| B002 | 14 | 0.386 | −0.007 |
| B003 | 15 | 0.247 | 0.017 |
| B004 | 21 | 0.554 | −0.022 |
| B005 | 4 | 0.189 | −0.217 |
| B006 | 28 | 0.317 | −0.082 |

FMEA base alone does not track where faults occur, which is expected because the generator makes FMEA
occurrence a noisy expert estimate. Adjusted risk is consistently positive because it adds change,
dependency and history signals. The correlation is moderate, not near-perfect, so ranking is still a real
inference problem. Phase 4 measures the effect on test selection directly.

## Failure fingerprints

Key: `component | test family | error code | failure stage`. Builds, variants and signal signatures are
attributes, so a recurring fault stays one family. IDs (`FF-001`…) follow first occurrence and stay stable as
history grows. FAIL executions without defects are listed separately as flaky or untriaged candidates.
