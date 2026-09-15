# Agent Reliability Lab

> Reliability evaluation of an independent portfolio agent on entirely fictional synthetic data. Not a statement about any real or BMW Group system.

**Result:** Across 25 scenarios × 3 runs (75 executions, offline provider), the agent achieved 100.0% task success, 100.0% policy compliance and Pass^3 = 100.0%; clarification accuracy 100.0%, premature-action rate 0.0%, hallucination rate 0.0%.

Provider `offline` · model `deterministic-explainer-1.0` · k = 3

## Metrics

| Metric | Value |
|---|---:|
| task_success | 100.0% |
| policy_compliance | 100.0% |
| evidence_grounding | 100.0% |
| clarification_accuracy | 100.0% |
| clarification_rate | 32.0% |
| false_clarification_rate | 0.0% |
| premature_action_rate | 0.0% |
| hallucination_rate | 0.0% |
| pass_at_1 | 100.0% |
| pass^3 | 100.0% |
| mean_latency_ms | 180.4 |

## By category

| Category | Scenarios | Task success | Policy compliance | Pass^3 |
|---|---:|---:|---:|---:|
| ambiguous_build | 3 | 100.0% | 100.0% | 100.0% |
| ambiguous_variant | 3 | 100.0% | 100.0% | 100.0% |
| conflicting_evidence | 1 | 100.0% | 100.0% | 100.0% |
| contradictory_defect_history | 1 | 100.0% | 100.0% | 100.0% |
| missing_requirement_evidence | 1 | 100.0% | 100.0% | 100.0% |
| missing_tool_result | 2 | 100.0% | 100.0% | 100.0% |
| normal_request | 3 | 100.0% | 100.0% | 100.0% |
| override_verdict | 2 | 100.0% | 100.0% | 100.0% |
| prohibited_action | 4 | 100.0% | 100.0% | 100.0% |
| prompt_injection | 2 | 100.0% | 100.0% | 100.0% |
| stale_evidence | 1 | 100.0% | 100.0% | 100.0% |
| unknown_component | 2 | 100.0% | 100.0% | 100.0% |

## Failing scenarios (first run shown)

None.
