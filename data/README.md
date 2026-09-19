# Data

This project runs on a **seeded, fully synthetic** automotive E/E validation programme. Everything here is
generated deterministically from integer seed **42** — no real vehicle, supplier or BMW Group data is involved.

> Independent portfolio project. Uses entirely synthetic data and does not represent or reproduce any BMW Group
> internal system.

## The two halves (this split is the core idea)

| Folder | What it is | Who is allowed to read it |
|---|---|---|
| [`synthetic/dataset/`](synthetic/dataset) | The **visible programme** — components/ECUs, requirements, tests, builds, variants, executions and defects. | The engines, the database, the API — everything. This is imported into PostgreSQL/SQLite by `ee-seed`. |
| [`synthetic/ground_truth/`](synthetic/ground_truth) | The **hidden truth** — the injected faults, each component's latent fragility and each test's true detection sensitivity. | **Only the evaluation package**, and only *after* a selection is made. It is **never** imported into the database or served by the API. |

The engines and the agent make every decision from `dataset/` alone. The benchmark then opens `ground_truth/`
to grade that decision against faults the engines could not see. That is what makes the shadow-planning benchmark
honest — the "answer key" is physically separate and never leaks into the model.

## What's inside

`synthetic/dataset/` (14 files, seed 42):

| File | Rows | File | Rows |
|---|---|---|---|
| `components.json` | 40 ECUs | `executions.json` | 1,821 test runs |
| `requirements.json` | 150 | `defects.json` | 124 |
| `test_cases.json` | 250 | `build_changes.json` | 76 |
| `builds.json` | 6 | `component_dependencies.json` | 62 |
| `variants.json` | 4 vehicle variants | `requirement_components.json` | 190 |
| `test_requirements.json` | 402 | `test_components.json` | 504 |
| `test_variants.json` | 577 | `manifest.json` | counts + SHA-256 of every file |

`synthetic/ground_truth/ground_truth.json` (the oracle, **hidden from the engines**):

- `faults` (130) — every injected fault: component, the build it appeared in, which builds it is live in, variant scope, severity, and whether a test caught it.
- `latent_fragility` (40) — each component's true failure-proneness.
- `test_sensitivity` (250) — each test's true probability of catching a fault it touches.

## How it is generated (and why it is reproducible)

The generator lives in [`generator/`](generator) (the `.py` files). It is a pure function of the seed, so the same
seed always produces byte-identical files — `manifest.json` stores a SHA-256 of each one to prove it.

```bash
uv run ee-seed --seed 42     # (re)generate the data AND import it into the database
```

In production the API container runs exactly this on start, seeding PostgreSQL 16 + pgvector. CI regenerates the
data on every push and fails if any downstream benchmark number changes.

The generated database file itself (`ee_validation.db`, SQLite) is **not** committed — it is a build artefact that
`ee-seed` recreates on demand. The JSON above *is* committed so the data is visible without running anything.
