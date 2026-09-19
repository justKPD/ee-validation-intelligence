# Agent Authority, Approval & Provenance (Phases 6–8)

## Authority model

| The agent may | The agent must never |
|---|---|
| inspect requirements, tests, results, defects | modify authoritative requirements |
| retrieve evidence and failure families | rewrite authoritative test definitions |
| explain risk | change PASS/FAIL verdicts |
| recommend tests and propose plans | close defects |
| ask for clarification | approve releases or its own recommendations |
| | silently execute tests |

The permissions live in [`config/agent_policy.toml`](../../config/agent_policy.toml); anything not listed is denied.
Every tool call, allowed or denied, is stored in `policy_decision`. Denials are also appended to the ledger.

### Risk-tiered autonomy

| Tier | Behaviour |
|---|---|
| read | automatic |
| recommend | persisted as `PROPOSED`; an engineer approves or rejects |
| modify | denied |
| verdict / release | never delegated |

## Request handling

| Request shape | Outcome |
|---|---|
| build + variant (or "all variants") are clear | `COMPLETED`: gather → rank → propose → explain |
| read-only question recognised by the question engine (`ee_agent/questions.py`) from the ids (TC-, R-, ECU-, B###, V#) and keywords it names; planning phrasing ("plan", "top N", "what should we test", "retest") always goes to the planner | `ANSWERED` by exactly one read-only tool, answer text written only from its result (no model); nothing proposed, run logged in the ledger. Kinds: test evidence (`get_test_evidence`), test history (`get_test_results`), requirement coverage (`get_requirement_evidence`), risk "why" (`explain_component_risk`), component defects (`get_component_defects`), build failures (`get_build_results`), build comparison (`compare_builds`), risk trend (`get_risk_trend`). Questions judged as of a build use the latest build when none is named and say so |
| build or variant missing, unknown or multiple; unknown component or test | `NEEDS_CLARIFICATION`, no plan tools called |
| prohibited intent (verdict change, close defect, release approval, requirement or test rewrite, approval, execution) | `REFUSED`; the attempted tool is `POLICY_DENIED` |
| injection-style instruction ("ignore previous instructions", "you are now", "bypass the policy") | `REFUSED`; `override_policy` denied |

## Recommendation lifecycle

```
PROPOSED ──► APPROVED ──► EXECUTED
    └──────► REJECTED (reason required)
```

Only a named human reviewer may decide; the agent actor is rejected. Invalid transitions return HTTP 409.

## Provenance ledger

`provenance_record` is append-only. Each entry stores `hash = sha256(prev_hash | type | subject | time | canonical payload)`,
and `/provenance/verify` recomputes the chain. Entry types are `AGENT_RUN`, `RECOMMENDATION_PROPOSED`,
`RECOMMENDATION_APPROVED`, `RECOMMENDATION_REJECTED`, `RECOMMENDATION_EXECUTED` and `POLICY_DENIED`.

A proposed recommendation records: build, variant, test, rank, priority score, estimated minutes, expected coverage gain,
reasons, source evidence ids (requirements, changes, executions, defects), component risk decomposition, ranking
contributions, model provider/name, prompt version, policy version, engine config versions, and the user request.
`/recommendations/{id}` returns it together with the full decision history.

## API

| Method | Path |
|---|---|
| POST | `/agent/plan` `{request, actor}` |
| GET | `/agent/runs`, `/agent/runs/{id}`, `/agent/tools` |
| GET | `/recommendations`, `/recommendations/{id}` |
| POST | `/recommendations/{id}/decision` `{decision, reviewer, reason, execution_reference}` |
| GET | `/provenance/ledger`, `/provenance/verify`, `/policy`, `/policy/decisions` |
