# ADR-001 — Monorepo, layered architecture

Status: Accepted (2026-09-15)

## Context
The platform has three pillars (Validation Intelligence, Agentic Test Management, AI Assurance) that must evolve independently while sharing one canonical data model.

## Decision
- One monorepo; Python packages form a **uv workspace**; the web app lives in `apps/web`.
- Layering (dependencies point downward only):
  1. `ee_domain` — schema, DTOs, session, telemetry
  2. `ee_etl`, `ee_generator` — data in
  3. `ee_risk`, `ee_coverage`, `ee_failures` — deterministic engines
  4. `ee_ranking` → `ee_evaluation` — prioritisation and benchmarks
  5. `ee_policies`, `ee_provenance`, `ee_agent` — agentic layer
  6. `ee_api` — HTTP composition root
- Engines are pure functions over an immutable `ValidationSnapshot` loaded *as of* a build, which makes them testable and leakage-safe.

## Consequences
Clear boundaries and replaceable engines. Cost: more `pyproject.toml` files.
