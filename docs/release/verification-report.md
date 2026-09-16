# Release Verification Report

*E/E Validation Intelligence & Agentic Test Control Tower*. This is an independent portfolio and research project built
only from public research and synthetic data. It has no BMW affiliation, used no internal access, and does not
reproduce any BMW system.

- **Date:** 2026-09-16
- **Verified commit:** `ef7f162` (clean tree before verification)
- **Machine:** local Windows workstation; Python 3.13.7 via uv; Node 24.13.0
- **Scope:** local verification only. No deployment, push, outreach or feature work was done.
- **Raw logs:** saved to the local temp folder (`%TEMP%\verify\*.log`) and not committed. The relevant output is quoted below.

## Summary

| Area | Result |
|---|---|
| Git state, quality gates (ruff, format, mypy, pytest) | **PASS**: 187 tests passed |
| Dataset reproducibility from seed 42 | **PASS**: all 13 dataset files byte-identical (sha256) |
| Shadow benchmark rerun | **PASS**: output JSON byte-identical to committed |
| Calibration rerun | **PASS**: output JSON and tuned config byte-identical |
| Reliability lab rerun | **PASS**: all metrics and outcomes identical; only wall-clock latency differs (expected) |
| Adversarial rerun | **PASS**: output JSON byte-identical; regression suite unchanged (28 fixed, 0 open) |
| API startup, planner flow, human approval persistence, provenance, `POLICY_DENIED` | **PASS** |
| Frontend startup and all 8 UI routes | **PASS** (one dev-mode first-load observation, not a defect) |
| Public naming and disclaimer | **PASS after one fix**: browser tab title changed to the full product name (uncommitted) |
| Docker / PostgreSQL / pgvector | **PASS** (validated 2026-09-17, see [docker-postgres-validation.md](docker-postgres-validation.md)) |
| GitHub Actions / Terraform / AWS | **NOT VERIFIED**: no remote, no Terraform binary, no AWS credentials |
| Discrepancies found in previously published text | **1**: hand-typed dataset sizes in the executive brief (see D1) |

---

## 1. Repository state

| Item | Command | Actual result | Status |
|---|---|---|---|
| Current branch | `git branch --show-current` | `main` | PASS |
| Working tree | `git status --short` | empty (clean) before verification | PASS |
| History | `git log --oneline` | see below (8 commits) | PASS |

```
ef7f162 docs(phase13-14): architecture, limitations, threat model, API reference, generated outreach
fce5309 feat(phase5,12): Next.js control tower UI and deployment foundation
03acac1 feat(phase11): learning & calibration study, admin config API
e08ff84 feat(phase9-10): agent reliability lab and search-based adversarial testing
1903dde feat(phase6-8): policy-gated agentic test planner, human approval and provenance ledger
c72afb4 feat(phase3-4): risk-based test ranking and shadow test planning benchmark
9f75e88 feat(phase2): validation intelligence core - risk, evidence coverage, failure fingerprints
42eb6e2 feat(phase0-1): project foundation and synthetic E/E data foundation
```

Remote: `git remote -v` prints nothing. No remote is configured and nothing has been pushed.

## 2. Quality gates

**Command:** `bash scripts/check.sh`. It runs `ruff check`, `ruff format --check`, `mypy packages apps/api/ee_api data/generator/ee_generator` and `pytest`.

| Item | Actual output | Status |
|---|---|---|
| ruff | `All checks passed!` | PASS |
| ruff format | `116 files already formatted` | PASS |
| mypy | `Success: no issues found in 58 source files` | PASS |
| pytest | `187 passed, 1 warning in 76.07s (0:01:16)` | PASS |
| exit code | `check_exit=0` | PASS |

The warning is a third-party deprecation notice from `starlette.testclient` (httpx → httpx2), not project code.

## 3. Dataset reproducibility

**Command:** regenerate with `generate_programme(42)` into a temporary directory, then compare `manifest.json` checksums against `data/synthetic/dataset/manifest.json`.

**Output:**
```
counts {'build_changes': 76, 'builds': 6, 'component_dependencies': 62, 'components': 40, 'defects': 124,
        'executions': 1821, 'requirement_components': 190, 'requirements': 150, 'test_cases': 250,
        'test_components': 504, 'test_requirements': 402, 'test_variants': 577, 'variants': 4}
sha256 identical for all files: True | generator 1.1.0
```
**Status:** PASS

## 4. Benchmark reruns

Before the reruns, the committed result files were extracted with `git show HEAD:<path>`. Each benchmark was then
rerun into its normal output path, and the files were compared field by field and with `git diff`.

| Benchmark | Command | Runtime | Exit | Output path | Result vs committed | Status |
|---|---|---|---|---|---|---|
| Calibration | `uv run ee-calibration` | 5 m 38.6 s | 0 | `benchmarks/calibration/results/latest.{json,md}`, `config/ranking.tuned.toml` | full JSON identical; tuned config identical | PASS |
| Shadow planning | `uv run ee-shadow` | 11.4 s | 0 | `benchmarks/shadow-planning/results/latest.{json,md}` | full JSON identical | PASS |
| Reliability lab | `uv run ee-reliability -k 3` | 14.3 s | 0 | `benchmarks/agent-reliability/results/latest.{json,md}` | identical except `latency_ms` fields | PASS (see D2) |
| Adversarial | `uv run ee-adversarial` | 13.5 s | 0 | `benchmarks/agent-reliability/results/adversarial.{json,md}`, `regressions.json` | full JSON identical; `regressions.json` unchanged | PASS |

The background task wrapper reported exit code 1. That came only from an invalid trailing `tail -3` flag in my
wrapper command; each benchmark's own exit code was 0, as shown above.

`git diff --stat` after all reruns lists only `benchmarks/agent-reliability/results/latest.{json,md}` (latency) and the
intentional title fix. No other result file changed by a single byte.

### Seed-42 headline metrics: previous vs. rerun

| Metric | Previously reported | Rerun | Equal |
|---|---:|---:|:---:|
| Critical-risk coverage at engineers' budget (risk-based) | 0.646 (64.6%) | 0.646 | ✓ |
| Critical-risk coverage, historical engineers | 0.4931 (49.3%) | 0.4931 | ✓ |
| Test-minutes saved to match engineers' yield | 0.4052 (reported "41%") | 0.4052 | ✓ |
| Builds where the yield was matched | 1.0 | 1.0 | ✓ |
| Critical-defect recall @K=10, risk-based | 0.1752 (17.5%) | 0.1752 | ✓ |
| Critical-defect recall @K=10, severity-first baseline | 0.0717 (7.2%) | 0.0717 | ✓ |
| Critical-defect recall @K=10, random baseline (20 seeds) | 0.1041 (10.4%) | 0.1041 | ✓ |
| Critical-defect recall at budget, risk-based / engineers | 0.6849 / 0.6918 | 0.6849 / 0.6918 | ✓ |
| Learned-model AUROC | 0.5993 | 0.5993 | ✓ |
| Engineering-score AUROC | 0.7041 | 0.7041 | ✓ |
| Reliability task success / policy compliance / Pass^3 | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 | ✓ |
| Adversarial mutants / failures / fixed regressions | 150 / 0 / 28 | 150 / 0 / 28 | ✓ |

Comparison script output: `ALL HEADLINE VALUES EQUAL: True`.

**Why exact equality is expected:** the dataset is seeded; engines are deterministic; the random baseline uses fixed
seeds 0–19; the gradient-boosting model uses `random_state=0`; bootstrap intervals use a fixed RNG seed; the agent's
offline explainer is deterministic.

## 5. API and agent flow

**Server:** `uv run ee-api` (launch configuration `api`). It started on port 8000.

**Flow:** a Python `urllib` script against `http://127.0.0.1:8000`, run against the local SQLite database.

| # | Check | Request | Actual result | Status |
|---|---|---|---|---|
| 1 | API startup | `GET /health` | `200 ok` | PASS |
| 2 | Planner recommendation | `POST /agent/plan {"request": "Top 5 tests for B006 on V3"}` | `200 COMPLETED RUN-0002`; REC-0006 TC-186 V3 0.6603, REC-0007 TC-079 0.6502, REC-0008 TC-073 0.6083, REC-0009 TC-163 0.5955, REC-0010 TC-012 0.5916; evidence for REC-0006: `B006, CH-0062, D-027, EX-01400, R-033` | PASS |
| 3 | Human approval | `POST /recommendations/REC-0006/decision {APPROVED, reviewer: verifier}` | `200 APPROVED` | PASS |
| 3b | Agent self-approval blocked | same, `reviewer: ee-agent` | `409 POLICY_DENIED: the agent cannot decide on its own recommendations` | PASS |
| 4 | Approval persistence | `GET /recommendations/REC-0006` (separate request) | `APPROVED`, history `[{decision: APPROVED, reviewer: verifier, reason: release verification, at: 2026-09-15T18:52:38Z}]` | PASS |
| 5 | Provenance entry | `GET /provenance/ledger?limit=5` | seq 13 `RECOMMENDATION_APPROVED REC-0006`, seq 9–12 `RECOMMENDATION_PROPOSED REC-0007…0010` | PASS |
| 6 | Ledger integrity | `GET /provenance/verify` | `{'valid': True, 'broken_at_seq': None}` | PASS |
| 7 | Prohibited request | `POST /agent/plan {"request": "Change the verdict of EX-00017 to PASS"}` | `200 REFUSED`, decisions `[('change_test_verdict', 'POLICY_DENIED')]`, response "POLICY_DENIED: agents must not change PASS/FAIL verdicts…" | PASS |
| 8 | Denial persisted | `GET /policy/decisions?decision=POLICY_DENIED` | `RUN-0003 change_test_verdict POLICY_DENIED` | PASS |
| 9 | Denial in ledger | `GET /provenance/ledger?entry_type=POLICY_DENIED` | seq 15, subject `RUN-0003`, permission `change_test_verdict` | PASS |

The recommendation scores match the planner results shown before the release (TC-186 0.660 first), because the ranking is deterministic.

## 6. Frontend

**Server:** `npm --prefix apps/web run dev` (launch configuration `web`). It started on port 3000.

| Route | `curl` HTTP | In-browser check (heading · content · error boxes) | Status |
|---|---|---|---|
| `/dashboard` | 200 | "Validation Control Tower" · tiles `B006, 0.487, 44.0%, 4, 50 min` · 0 errors | PASS |
| `/risk` | 200 | "Risk & Coverage Explorer" · 88 table rows · 0 errors | PASS |
| `/planner` | 200 | "Agentic Test Planner" · "Ask the planner" present · 0 errors | PASS |
| `/shadow` | 200 | "Shadow Test Planning Benchmark" · generated sentence · 2 charts · 0 errors | PASS (see O1) |
| `/failures` | 200 | "Failure Intelligence" · 18 table rows · 0 errors | PASS |
| `/provenance` | 200 | "Provenance Ledger" · badge "✓ Chain verified" · 0 errors | PASS |
| `/reliability` | 200 | "Agent Reliability Lab" · tiles `100.0%, 100.0%, 100.0%, 100.0%, 0.0%` · 0 errors | PASS |
| `/admin` | 200 | "Admin: Model, Policy & Configuration" · 7 `POLICY DENIED` permission rows · 0 errors | PASS |

**Browser console:** no errors. Only React DevTools notices and Fast Refresh logs.
**Production build:** passed at `fce5309` (`npm run build`: 12 static pages); not rebuilt in this pass.

## 7. Public naming and disclaimers

| Check | Command / method | Result | Status |
|---|---|---|---|
| Product name | README title, API title, nav, browser title | README: "E/E Validation Intelligence & Agentic Test Control Tower". API: "E/E Validation Intelligence API". Nav: "E/E Validation Intelligence / Agentic Test Control Tower". **Browser title was "E/E Validation Control Tower"**; changed to the full name and confirmed with `document.title` | PASS after fix (uncommitted) |
| Repository/package name | `pyproject.toml` | `name = "ee-validation-intelligence"` | PASS |
| Local folder name `bmw` in tracked content | `git grep -n -i bmw` (including lockfiles) | no path or folder references; the only non-disclaimer match is README rule "no implied BMW affiliation" | PASS |
| Local path / username leaks | `git grep -E "Downloads\|uc\.1\.27\.25\|task 3\|[A-Z]:\\\\"` | no matches | PASS |
| Disclaimer present | `git grep -c "BMW Group"` | present in README, API description, web footer, all benchmark reports, outreach documents, limitations | PASS |
| No affiliation or internal-access claims | manual review of README and `docs/outreach/*` | all describe an independent project inspired by public research on synthetic data | PASS |

The local working folder is still called `bmw` on disk. That name does not appear in any tracked file, so it is not
published. Clone into `ee-validation-intelligence` when creating the GitHub repository.

## 8. Not verifiable in this environment

| Item | Why | Status |
|---|---|---|
| `docker compose up --build` | Docker was not installed at the time of this pass | **Later VERIFIED** on 2026-09-17; see [docker-postgres-validation.md](docker-postgres-validation.md) |
| GitHub Actions workflow | no remote repository; never run | NOT VERIFIED |
| Terraform `fmt` / `validate` / `apply` | no Terraform binary, no AWS credentials | NOT VERIFIED |
| PostgreSQL migrations and seed | no local PostgreSQL at the time of this pass | **Later VERIFIED** on 2026-09-17: PostgreSQL 16.15, migrations `0001 -> 0002` |
| Live Claude provider | no credentials; covered by fake-client tests only | NOT VERIFIED |

---

## Discrepancies and observations

**D1: hand-typed dataset sizes in published text (discrepancy).**
`scripts/build_brief.py` writes "about 1,800 executions and about 110 defects" as fixed text, and the same wording
appears in `docs/outreach/executive-brief.md` and in my completion report. The regenerated dataset has
**1,821 executions (close) and 124 defects (the "about 110" is wrong)**. The reason: I wrote those sizes from memory
of an earlier generator-tuning run instead of reading the manifest. This breaks the project's "no hand-typed numbers" rule.
**Not fixed in this pass.** Proposed fix: read the counts from `data/synthetic/dataset/manifest.json` in `build_brief.py` and regenerate.

**D2: reliability report is not byte-reproducible (expected).**
`mean_latency_ms` was 180.4 before and 105.2 on rerun, and per-run `latency_ms` values differ. Wall-clock latency
depends on machine load (calibration had just finished). Every scenario status, check and success metric is identical.
Proposed fix: move latency out of the committed report, or exclude it from reproducibility checks and document that.
The rerun file is currently uncommitted.

**O1: first dev-mode load of `/shadow` (observation, not a defect).**
With a 6-second wait, the first browser check found no heading yet. `/benchmarks/shadow` returned 200 with valid JSON,
and the results file was not being rewritten at the time. With a 10-second wait the page rendered fully: heading, sentence, both charts, no errors.
The cause is Next.js dev-mode on-demand compilation. The production build prerenders the page.

**O2: verification wrote to the local database.** RUN-0002, RUN-0003 and REC-0006…0010 now exist in `ee_validation.db`.
It is gitignored; `uv run ee-seed` does not clear agentic tables.

## Uncommitted changes after this pass

| File | Change |
|---|---|
| `apps/web/app/layout.tsx` | browser title → "E/E Validation Intelligence & Agentic Test Control Tower" |
| `benchmarks/agent-reliability/results/latest.{json,md}` | latency values only (D2) |
| `docs/release/verification-report.md` | this report |

---

## Release hardening (follow-up, same day)

Fixes for D1 and D2, then a full rerun.

| # | Fix | Change | Status |
|---|---|---|---|
| D1 | Hand-typed dataset sizes | `scripts/build_brief.py` now reads component, requirement, test, build, variant, execution and defect counts from `data/synthetic/dataset/manifest.json`. It refuses to run if the dataset seed differs from the benchmark seed. Regenerated brief: "40 fictional ECUs, 150 requirements, 250 tests, 6 builds, 4 variants, 1,821 executions and 124 defects". | FIXED |
| D2 | Wall-clock timing in committed reliability results | `latency_ms` removed from `RunOutcome` and `mean_latency_ms` from metrics. Timing now goes to `benchmarks/agent-reliability/results/diagnostics.json`, marked `non_deterministic: true` and gitignored. Timing also stripped from the committed pre-fix baseline; its stable metrics are unchanged. New test `tests/test_reliability_reproducibility.py` requires two runs to write byte-identical `latest.json` and `latest.md`. | FIXED |
| — | Browser title | `apps/web/app/layout.tsx` title = "E/E Validation Intelligence & Agentic Test Control Tower" | KEPT |

### Rerun after fixes

| Item | Command | Actual result | Status |
|---|---|---|---|
| ruff | `bash scripts/check.sh` | `All checks passed!` · `118 files already formatted` | PASS |
| mypy | same | `Success: no issues found in 58 source files` | PASS |
| pytest | same | `188 passed, 1 warning in 109.42s` (187 + 1 new reproducibility test) | PASS |
| Calibration | `uv run ee-calibration` | exit 0; `latest.json` and `config/ranking.tuned.toml` identical to committed | PASS |
| Shadow | `uv run ee-shadow` | exit 0; `latest.json` identical to committed | PASS |
| Reliability | `uv run ee-reliability -k 3` | exit 0; all stable metrics and all 75 outcomes identical to committed (timing fields removed); no `latency` in `latest.json` | PASS |
| Adversarial | `uv run ee-adversarial` | exit 0; `adversarial.json` and `regressions.json` identical (150 mutants, 0 failures, 28 fixed) | PASS |
| Brief | `uv run python scripts/build_brief.py` | exit 0; counts come from the manifest | PASS |

### Stable seed-42 metrics after fixes

| Metric | Before fixes | After fixes | Equal |
|---|---:|---:|:---:|
| Critical-risk coverage at engineers' budget | 0.646 | 0.646 | ✓ |
| Test-minutes saved share | 0.4052 | 0.4052 | ✓ |
| Critical-defect recall @K=10: risk-based / severity-first / random | 0.1752 / 0.0717 / 0.1041 | 0.1752 / 0.0717 / 0.1041 | ✓ |
| Learned-model AUROC / engineering-score AUROC | 0.5993 / 0.7041 | 0.5993 / 0.7041 | ✓ |
| Reliability stable metrics (10 fields incl. task success, policy compliance, Pass^3) | all 1.0 / 0.32 clarification rate / 0.0 error rates | identical | ✓ |

### Docker / PostgreSQL validation

At the time of this pass: blocked, because Docker was not installed (`docker: command not found`).

**Completed on 2026-09-17** after Docker Desktop was installed. Full evidence: [docker-postgres-validation.md](docker-postgres-validation.md).

| Item | Result |
|---|---|
| Docker Desktop stack | `docker compose up --build`: database, API and web healthy |
| PostgreSQL | 16.15, validated from an empty database |
| pgvector | 0.8.6 installed and tested (distance operators, nearest-neighbour ordering) |
| Alembic migrations | `0001 -> 0002` succeeded; 18 tables, 20 foreign keys |
| Seed-42 counts | 40 components/ECUs · 150 requirements · 250 tests · 6 builds · 4 variants · 1,821 executions · 124 defects: exact |
| Record-level match | all 13 seeded tables equal the source dataset record for record |
| Tests | 188 passed against PostgreSQL; 47 database-backed tests separately re-run on PostgreSQL; standard SQLite path 188 passed; ruff and mypy pass |
| UI | all 8 routes return 200 and render real PostgreSQL-backed data |
| Agent flows | planner, approval, provenance and `POLICY_DENIED` validated; hash chain valid; state persisted across a Docker restart |
| Stable metrics | 0.646 · 0.4052 · CriticalDefectRecall@10 0.1752 / 0.0717 / 0.1041 · AUROC 0.5993 / 0.7041 · reliability unchanged · adversarial 150 mutants / 0 failures / 28 fixed: unchanged |
| Infrastructure fixes | missing `.dockerignore`; `uv` version mismatch; API startup via `uv run`; missing health checks; folder-name leakage into Docker resource names; PostgreSQL test support via `EE_TEST_DATABASE_URL` |
| Operational note | Docker objects about 1.87 GB after cleanup; `docker_data.vhdx` stays around 5.63 GB (optional compaction, unrelated to correctness) |
