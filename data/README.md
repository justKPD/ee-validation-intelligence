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

## Sample records

Real rows from the seed-42 files (so you can see the shape without opening the big JSON). They also tell one story:
on build **B006**, component **ECU-TPMS** changed heavily, so the test that touches it (**TC-186**) ranks first.

**Visible programme** (`synthetic/dataset/`):

```jsonc
// components.json  — a fictional ECU
{ "id": "ECU-BCM", "name": "Bcm (fictional)", "asil": "B", "domain": "body", "supplier": "Fictional Supplier Alpha" }

// builds.json  — 6 software builds over time
{ "id": "B006", "sequence": 6, "release_date": "2026-04-27", "build_family": "26.03" }

// variants.json  — 4 vehicle variants
{ "id": "V3", "name": "Fictional BEV Performance", "powertrain": "BEV", "market": "EU", "features": "hv,adas_l2_plus,air_suspension,hud" }

// build_changes.json  — what changed in a build (this drives "recent change" risk)
{ "id": "CH-0062", "build_id": "B006", "target_type": "component", "target_id": "ECU-TPMS", "change_kind": "feature", "magnitude": 0.96 }

// requirements.json  — FMEA impact/occurrence/detectability + severity
{ "id": "R-033", "title": "TPMS shall provide state-of-charge within specified operating range",
  "fmea_impact": 5, "fmea_occurrence": 7, "fmea_detectability": 6, "severity": 2, "revision": 1, "created_build_id": "B001" }

// test_cases.json  — a test (level SIL/HIL, duration, family)
{ "id": "TC-186", "name": "perception check for SURROUND_VIEW #186", "level": "SIL", "test_family": "perception", "duration_min": 5.0, "automated": true }

// link tables — which requirement/component/variant each test covers
// requirement_components.json:  { "requirement_id": "R-033", "component_id": "ECU-TPMS" }
// test_components.json:         { "test_id": "TC-186", "component_id": "ECU-TPMS" }
// test_variants.json:           { "test_id": "TC-186", "variant_id": "V3" }
// component_dependencies.json:  { "upstream_id": "ECU-BCM", "downstream_id": "ECU-BMS", "kind": "gateway_route" }

// executions.json  — a test that was actually run (verdict PASS/FAIL)
{ "id": "EX-00004", "build_id": "B001", "test_id": "TC-130", "variant_id": "V1", "verdict": "FAIL",
  "selected_by": "HISTORICAL_ENGINEER", "requirement_revision": 1, "duration_min": 70.4 }

// defects.json  — a defect produced by a failing execution
{ "id": "D-001", "component_id": "ECU-BMS", "execution_id": "EX-00004", "severity": 5, "error_code": "ED93C" }
```

**Hidden ground truth** (`synthetic/ground_truth/ground_truth.json` — the engines never see this):

```jsonc
// faults[] — an injected fault and whether a test caught it
{ "id": "F-0001", "component_id": "ECU-BMS", "injected_build": "B001", "live_builds": ["B001"],
  "variant_scope": ["V1","V2","V3","V4"], "severity": 5, "detected": true, "detected_by": "EX-00004" }

// latent_fragility — each component's TRUE failure-proneness (0–1)
"ECU-TPMS": 0.017      // note: TPMS changed a lot in B006 but is intrinsically low-fragility

// test_sensitivity — each test's TRUE chance of catching a fault it touches (0–1)
"TC-186": 0.3881
```

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
