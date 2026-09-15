# E/E Validation Intelligence & Agentic Test Control Tower

**Risk-Based Test Prioritization, Evidence Traceability & Policy-Gated Agentic Test Management**

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research.
> It uses **entirely synthetic data** and does not represent or reproduce any BMW Group internal system.
> It has no affiliation with the BMW Group.

## The problem

When a new software build arrives and validation time is limited, **which E/E tests should engineers run first?**
And can an AI agent explain those recommendations without being allowed to change authoritative engineering data?

**Results at a glance:** [executive brief](docs/outreach/executive-brief.md). Every number in it is generated from
the benchmark runs by `scripts/build_brief.py`, including what the results do *not* show.

## Three pillars

| Pillar | What it does | Results |
|---|---|---|
| **Validation Intelligence** | explainable risk, evidence-aware coverage (CURRENT/STALE/INCOMPATIBLE/MISSING/FAILED), failure fingerprints, risk-based test ranking | [shadow planning](benchmarks/shadow-planning/results/latest.md) |
| **Agentic Test Management** | LangGraph planner, MCP-compatible tools, default-deny policy gate, human approval, hash-chained provenance ledger | [policy & provenance](docs/methodology/agent-policy-and-provenance.md) |
| **AI Assurance** | leakage-safe shadow replay, reliability lab (Pass^k), adversarial search, calibration and dev-seed tuning | [reliability](benchmarks/agent-reliability/results/latest.md) · [adversarial](benchmarks/agent-reliability/results/adversarial.md) · [calibration](benchmarks/calibration/results/latest.md) |

## Quick start

```bash
pip install uv
uv sync
uv run ee-seed --seed 42              # migrate + generate + validate + import + dataset summary
uv run ee-api                         # API on http://127.0.0.1:8000 (docs at /docs)
npm --prefix apps/web install
npm --prefix apps/web run dev         # UI on http://localhost:3000
bash scripts/check.sh                 # ruff + format + mypy + pytest (same as CI)
```

Reproduce every result from the seed:

```bash
uv run ee-shadow                      # shadow test planning benchmark
uv run ee-reliability -k 3            # agent reliability lab
uv run ee-adversarial                 # adversarial search + regression suite
uv run ee-calibration                 # calibration, dev-seed tuning, overrides, bootstrap CIs (several minutes)
uv run python scripts/build_brief.py  # regenerate outreach documents from results
```

Docker (PostgreSQL 16 + pgvector, API, web): `docker compose up --build`.
Use Claude for explanations: `EE_MODEL_PROVIDER=anthropic uv run ee-api`. The default is a deterministic offline explainer.

## UI routes

`/dashboard` Control Tower · `/risk` Risk & Coverage · `/planner` Agentic Test Planner · `/shadow` Shadow Planning ·
`/failures` Failure Intelligence · `/provenance` Provenance Ledger · `/reliability` Agent Reliability Lab · `/admin` Policy & Config

## Phase status

| Phase | Status |
|---|---|
| 0 Project foundation | done: uv workspace, ruff/mypy/pytest, CI workflow, Docker, OpenTelemetry, ADRs |
| 1 Data foundation | done: schema + migrations, seeded generator with hidden fault model, ETL + data quality, browse API |
| 2 Validation intelligence core | done: risk, evidence coverage, failure fingerprints, as-of snapshots |
| 3 Test ranking | done: engineering ranker, severity/random baselines, learned model, hybrid |
| 4 Shadow test planning | done: counterfactual oracle scoring, equal-budget comparison, observed replay |
| 5 Full UI | done: eight routes, verified against the running API |
| 6–8 Agent, authority, provenance | done: LangGraph planner, policy gate, approval lifecycle, hash-chained ledger |
| 9 Reliability lab | done: 25 scenarios × k runs, Pass^k and grounding metrics |
| 10 Adversarial testing | done: 14 mutators, failure classes, open → fixed regression suite |
| 11 Learning & calibration | done: calibration, dev-seed tuning with held-out check, overrides, bootstrap CIs |
| 12 Deployment | authored: Docker, GitHub Actions, Terraform for AWS. **Not executed**: no Docker, CI remote or AWS credentials in the build environment |
| 13 Documentation | done: architecture, methodology, ADRs, API reference, limitations, threat model |
| 14 Portfolio / outreach | done: generated executive brief, recruiter and researcher summaries, demo script |

## Documentation

- [Architecture](docs/architecture/architecture.md) · [ADRs](docs/adr) · [API reference](docs/api/api-reference.md)
- Methodology: [synthetic data](docs/methodology/synthetic-data.md) · [risk & evidence](docs/methodology/risk-and-evidence.md) ·
  [ranking & shadow planning](docs/methodology/ranking-and-shadow-planning.md) · [agent policy & provenance](docs/methodology/agent-policy-and-provenance.md) ·
  [reliability & adversarial](docs/methodology/agent-reliability-and-adversarial-testing.md) · [dataset summary](docs/methodology/dataset-summary.md)
- [Limitations](docs/limitations.md) · [Threat model](docs/threat-model.md)
- Outreach: [executive brief](docs/outreach/executive-brief.md) · [recruiter summary](docs/outreach/recruiter-summary.md) ·
  [researcher summary](docs/outreach/researcher-summary.md) · [demo script](docs/outreach/demo-script.md)

## Non-negotiable rules this codebase enforces

1. Synthetic data only; no implied BMW affiliation.
2. Deterministic engines own authoritative calculations; agents recommend, explain and orchestrate.
3. Agents never modify requirements, test definitions or verdicts, close defects, or approve releases (`POLICY_DENIED`, logged).
4. No hard-coded metrics: every reported number comes from a run.
5. No future leakage: as-of-build snapshots, enforced by tests.
