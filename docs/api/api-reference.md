# API Reference

Generated from the FastAPI OpenAPI schema (E/E Validation Intelligence API 0.1.0). Interactive docs: `/docs` on a running API. Full schema: [openapi.json](openapi.json).

## admin

| Method | Path | Query parameters |
|---|---|---|
| GET | `/config` | — |

## agent

| Method | Path | Query parameters |
|---|---|---|
| POST | `/agent/plan` | — |
| GET | `/agent/runs` | limit |
| GET | `/agent/runs/{run_id}` | — |
| GET | `/agent/tools` | — |
| GET | `/policy` | — |
| GET | `/policy/decisions` | decision, limit |
| GET | `/provenance/ledger` | entry_type, limit, offset |
| GET | `/provenance/verify` | — |
| GET | `/recommendations` | status, build_id, limit |
| GET | `/recommendations/{recommendation_id}` | — |
| POST | `/recommendations/{recommendation_id}/decision` | — |

## catalog

| Method | Path | Query parameters |
|---|---|---|
| GET | `/builds` | — |
| GET | `/builds/{build_id}` | — |
| GET | `/components` | domain, asil, limit, offset |
| GET | `/components/{component_id}` | — |
| GET | `/defects` | component_id, build_id, status, min_severity, limit, offset |
| GET | `/executions` | build_id, variant_id, test_id, verdict, limit, offset |
| GET | `/requirements` | component_id, category, min_severity, limit, offset |
| GET | `/requirements/{requirement_id}` | — |
| GET | `/stats` | — |
| GET | `/tests` | component_id, requirement_id, level, family, limit, offset |
| GET | `/tests/{test_id}` | — |
| GET | `/variants` | — |

## intelligence

| Method | Path | Query parameters |
|---|---|---|
| GET | `/builds/{build_id}/coverage` | — |
| GET | `/builds/{build_id}/evidence` | status, variant_id, requirement_id, component_id |
| GET | `/builds/{build_id}/failure-families` | component_id, recurring_only |
| GET | `/builds/{build_id}/risk/components` | — |
| GET | `/builds/{build_id}/risk/components/{component_id}` | — |
| GET | `/builds/{build_id}/risk/requirements` | critical_only |

## ops

| Method | Path | Query parameters |
|---|---|---|
| GET | `/health` | — |

## ranking

| Method | Path | Query parameters |
|---|---|---|
| GET | `/benchmarks/shadow` | — |
| GET | `/builds/{build_id}/ranking` | strategy, limit, variant_id, budget_minutes, seed |
| GET | `/builds/{build_id}/ranking/model` | — |

## reliability

| Method | Path | Query parameters |
|---|---|---|
| GET | `/benchmarks/adversarial` | — |
| GET | `/benchmarks/reliability` | — |
