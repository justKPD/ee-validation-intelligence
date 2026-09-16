# Docker / PostgreSQL Validation

*E/E Validation Intelligence & Agentic Test Control Tower*. This is an independent portfolio and research project
built only from public research and synthetic data. It has no BMW affiliation and does not reproduce any BMW system.

- **Date:** 2026-09-17
- **Base commit:** `e30af7f` plus the release/infrastructure fixes listed below (uncommitted at time of writing)
- **Machine:** Windows 10 Pro x86_64; Docker Desktop, engine 29.8.0 (WSL 2, overlayfs, 4 CPUs, ~9.6 GB RAM); Docker Compose v5.5.1
- **Scope:** local containers only. No GitHub push, AWS deployment, outreach or feature work.
- **Raw logs:** the local temp folder `%TEMP%\dockerval\` (not committed). The relevant output is quoted below.

## Summary

| Area | Result |
|---|---|
| A. Docker build and startup | **PASS**: both images built; db, API and web all healthy |
| B. PostgreSQL + pgvector + migrations | **PASS**: PostgreSQL 16.15, pgvector 0.8.6 usable; migrations 0001→0002 on an empty database |
| C. Seed-42 data in PostgreSQL | **PASS**: all counts exact, and all 13 tables record-for-record equal to the verified seed-42 files |
| D. PostgreSQL integration tests | **PASS**: 188-test suite exit 0 with PostgreSQL; 47 database-backed tests re-run verbosely: `47 passed` |
| E. Containerized API + 8 UI routes | **PASS**: all 200; real data; 0 error boxes; no console errors |
| F. Planner, approval, policy denial | **PASS** |
| G. Provenance chain | **PASS**: `valid: true` after all operations and after restart |
| H. Benchmark stability | **PASS**: every stable metric identical, computed from data read back out of PostgreSQL |
| I. Persistence after restart | **PASS**: agentic and engineering state identical before and after |
| Disk constraint (~5 GB) | **PASS for Docker objects** (peak 4.31 GB; final 1.87 GB). **Physical WSL disk file is 5.63 GB** (see Disk) |
| Defects found and fixed | 5 release/infrastructure defects (see Fixes) |

---

## 0. Pre-checks

| Item | Command | Actual result | Status |
|---|---|---|---|
| Docker CLI / engine | `docker info` | first attempt: `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` (Docker Desktop installed per-user at `%LOCALAPPDATA%\Programs\DockerDesktop` but not running). After `Start-Process "Docker Desktop.exe"`: `server=29.8.0 os=Docker Desktop arch=x86_64 cpus=4 driver=overlayfs`, ready after ~10 s | PASS after start |
| Compose | `docker compose version` | `Docker Compose version v5.5.1` | PASS |
| Virtualization | `Win32_ComputerSystem.HypervisorPresent` | `True`; WSL distro `docker-desktop` version 2 (the firmware flag reads False once Hyper-V owns virtualization) | PASS |
| Free disk | `Get-PSDrive` | C: 11.49 GB free, D: 4.57 GB free | PASS |
| Ports | `Get-NetTCPConnection -LocalPort 5432/8000/3000 -State Listen` | all free | PASS |
| Starting state | `docker system df` | 0 images, 0 containers, 0 volumes, 0 build cache | — |

## Fixes (release/infrastructure defects only)

| # | Defect | Impact if unfixed | Fix |
|---|---|---|---|
| F1 | No `.dockerignore` | `COPY . .` would send host `node_modules`, `.next`, `.venv`, `.git` and the SQLite DB into the build context and images. The web image would also get Windows `node_modules` binaries, breaking `next build`. | Added `.dockerignore` |
| F2 | API image copied uv **0.5** while `uv.lock` was written by uv **0.12.15** | `uv sync --frozen` could reject the lockfile | `COPY --from=ghcr.io/astral-sh/uv:0.12.15`; `UV_NO_CACHE=1` to keep the image lean |
| F3 | API started with `uv run …` | a runtime re-resolve on every container start | runs the installed `.venv/bin` entry points (`ee-seed`, `ee-api`) directly |
| F4 | No API or web healthchecks; web did not wait for a healthy API | "service healthy" could not be verified | `HEALTHCHECK` on `/health` in the API image; compose healthcheck on the web `/dashboard`; `web` depends on `api: service_healthy` |
| F5 | Compose project name came from the local folder | containers, network and volume were named `bmw-db-1`, `bmw_pgdata`, which leaks the local folder name | `name: ee-validation-intelligence` in `docker-compose.yml`. The first, empty (0-table) `bmw_*` db container, network and volume created by this run were removed before continuing. |
| T1 | Integration tests could only run on SQLite | PostgreSQL integration could not be tested | root `conftest.py`: set `EE_TEST_DATABASE_URL` to run the database-backed tests on PostgreSQL. It refuses any database not named `*_test` and resets that test database's `public` schema per session. |

**No SQLite-specific application defects surfaced under PostgreSQL.** String lengths, foreign keys, datetimes, JSON
text columns, migrations and hash-chained ledger ordering all behaved identically, so no application code was changed.

## A. Docker build and startup

| Item | Command | Actual result | Status |
|---|---|---|---|
| Build | `docker compose build --progress=plain` | `build_exit=0`, 11 m 35.6 s (cold, no cache); Next.js build generated 12/12 static pages inside the image | PASS |
| Stack | `docker compose up --build -d` | `up_exit=0`; api `Healthy` → web started | PASS |
| Health | `docker compose ps` | all healthy within ~10 s of the last container start (see below) | PASS |

```
NAME                               IMAGE                                  STATUS                    PORTS
ee-validation-intelligence-api-1   ee-validation-intelligence-api:local   Up 18 seconds (healthy)   0.0.0.0:8000->8000/tcp
ee-validation-intelligence-db-1    pgvector/pgvector:pg16                 Up 7 minutes (healthy)    0.0.0.0:5432->5432/tcp
ee-validation-intelligence-web-1   ee-validation-intelligence-web:local   Up 7 seconds (healthy)    0.0.0.0:3000->3000/tcp
```

API container startup log:
```
Imported 4206 records into postgresql+psycopg://ee:ee_local_only@db:5432/ee_validation
Uvicorn running on http://0.0.0.0:8000
```

### Image sizes

| Image | ID | Size |
|---|---|---|
| `ee-validation-intelligence-api:local` (python:3.12-slim + uv-installed venv incl. scikit-learn, LangGraph) | `d4aff7115049` | 850 MB |
| `ee-validation-intelligence-web:local` (node:22-alpine, standalone Next.js) | `6bde642fae8b` | 317 MB |
| `pgvector/pgvector:pg16` | `ccc6e83d6e35` | 621 MB |

## B. PostgreSQL, pgvector and migrations

| Item | Command | Actual result | Status |
|---|---|---|---|
| Version | `psql -c "select version();"` | `PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) on x86_64-pc-linux-gnu … 64-bit` | PASS |
| Empty start | `select count(*) from information_schema.tables where table_schema='public'` | `0` (new volume) | PASS |
| pgvector available | `select name, default_version from pg_available_extensions where name='vector'` | `vector \| 0.8.6` | PASS |
| pgvector usable | `create extension if not exists vector;` `select '[1,2,3]'::vector <-> '[1,2,4]'`, `'[1,0]'::vector <=> '[0,1]'`; temp `vector(3)` table with an `ORDER BY emb <-> '[1,1,2]'` query | `CREATE EXTENSION`; `vector 0.8.6`; L2 = 1, cosine = 1; nearest row id = 1 (correct) | PASS |
| Migrations | the API container runs `ee-seed` → `alembic upgrade head` on the empty database | `alembic_version` = `0002`; 18 application tables + `alembic_version` | PASS |
| Foreign keys | `information_schema.table_constraints where constraint_type='FOREIGN KEY'` | 20 | PASS |
| FK enforcement | `insert into defect(... component_id='ECU-NOPE' ...)` | `ERROR: … violates foreign key constraint "defect_component_id_fkey"` | PASS |

The schema does not use pgvector yet. The extension was created in the application database only to prove it is usable. It is not part of the Alembic migrations.

## C. Seed-42 dataset in PostgreSQL

**Command:** per-table `select count(*)` in `ee_validation`.

| Table | Expected | PostgreSQL | Status |
|---|---:|---:|---|
| components | 40 | 40 | PASS |
| requirements | 150 | 150 | PASS |
| test cases | 250 | 250 | PASS |
| builds | 6 | 6 | PASS |
| variants | 4 | 4 | PASS |
| executions | 1,821 | 1,821 | PASS |
| defects | 124 | 124 | PASS |
| build changes / dependencies / req-components / test-reqs / test-components / test-variants | 76 / 62 / 190 / 402 / 504 / 577 | 76 / 62 / 190 / 402 / 504 / 577 | PASS |

**Orphan checks:** all 0 (execution → test/build/variant, defect → execution/component, defect on a non-FAIL execution).

**Record-level comparison.** Every row was loaded back from PostgreSQL (`load_dataset_view`) and compared, as canonical
JSON, with a fresh `generate_programme(42)`. Output: `PG dataset equals seed-42 files, per table: {... all True}`, `ALL TABLES EQUAL: True`.

## D. PostgreSQL integration tests

A dedicated database `ee_validation_test` was created (`create database ee_validation_test;`). The application database was never reset.

| Item | Command | Actual result | Status |
|---|---|---|---|
| Full suite with PostgreSQL | `EE_TEST_DATABASE_URL=postgresql+psycopg://ee:…@localhost:5432/ee_validation_test uv run pytest -p no:warnings -q` | 188 tests collected and run, `pytest_exit=0`, 4 m 54.6 s. The `-q` summary line was not captured, so see the next row. | PASS |
| Database-backed subset, verbose | same env; `uv run pytest tests/test_etl.py tests/test_snapshot.py apps/api/tests -v` | `47 passed, 1 warning in 26.97s` | PASS |
| Proof tests used PostgreSQL | query `ee_validation_test` after the run | `alembic 0002`, components 40, executions 1,821, defects 124, agent_run 3, recommendation 3, approval 1, policy_decision 6, provenance_record 8 | PASS |
| Default path unaffected | `bash scripts/check.sh` (SQLite) | ruff pass, `118 files already formatted`, mypy `no issues found in 58 source files`, `188 passed` | PASS |

What PostgreSQL covered:
- migrations (fixture `alembic upgrade head` on an empty schema)
- foreign-key integrity
- import/ETL (checksum, schema, dangling-reference and rollback tests)
- snapshot equality between DB and files
- all read APIs
- agentic tables, approvals (including self-approval refusal), provenance ledger and chain verification
- policy logs

Unit tests that create their own isolated SQLite databases (policy, provenance service, agent) still use SQLite by design.

## E. Containerized API and frontend

The web container (`NEXT_PUBLIC_API_URL=http://localhost:8000`) talks to the API container, which talks to PostgreSQL.

| Route | `curl -w '%{http_code}'` | Browser (heading · data · error boxes) | Status |
|---|---|---|---|
| `/dashboard` | 200 | "Validation Control Tower" · tiles `B006, 0.487, 44.0%, 4, 50 min` · 0 | PASS |
| `/risk` | 200 | "Risk & Coverage Explorer" · 88 table rows · 0 | PASS |
| `/planner` | 200 | "Agentic Test Planner" · build/variant selectors populated (11 options) · 0 | PASS |
| `/shadow` | 200 | "Shadow Test Planning Benchmark" · generated sentence · 2 charts · 0 | PASS |
| `/failures` | 200 | "Failure Intelligence" · 18 rows · 0 | PASS |
| `/provenance` | 200 | "Provenance Ledger" · "✓ Chain verified" · 14 rows · 0 | PASS |
| `/reliability` | 200 | "Agent Reliability Lab" · `100.0%, 100.0%, 100.0%, 100.0%, 0.0%` · 0 | PASS |
| `/admin` | 200 | "Admin: Model, Policy & Configuration" · 7 `POLICY DENIED` rows · 0 | PASS |

Browser title: "E/E Validation Intelligence & Agentic Test Control Tower". Console (`read_console_messages`, errors only): no messages.

## F. End-to-end planner flow against the containers

**Command:** a Python `urllib` script against `http://127.0.0.1:8000`.

| # | Step | Request | Actual result | Status |
|---|---|---|---|---|
| 0 | Stats | `GET /stats` | components 40, requirements 150, test_cases 250, builds 6, variants 4, build_changes 76, executions 1821, defects 124 | PASS |
| 1 | Ranked tests | `GET /builds/B006/ranking?variant_id=V3&limit=5` | TC-186 0.6603, TC-079 0.6502, TC-073 0.6083, TC-163 0.5955, TC-012 0.5916 (identical to the SQLite verification) | PASS |
| 1b | Plan | `POST /agent/plan {"request":"Top 5 tests for B006 on V3"}` | `200 COMPLETED RUN-0001`, REC-0001…REC-0005 | PASS |
| 2 | Evidence | `GET /recommendations/REC-0001` | sources `B006, CH-0062, D-027, EX-01400, R-033`; reasons "ECU-TPMS changed in B006 (feature, magnitude 0.96)", "R-033 evidence on V3 is STALE", "test revealed 1 defect(s) in earlier builds"; risk ECU-TPMS 0.4604 | PASS |
| 3 | Approve | `POST /recommendations/REC-0001/decision {APPROVED, docker-verifier}` | `200 APPROVED` | PASS |
| 4 | Re-read | `GET /recommendations/REC-0001` | `APPROVED`, history `[{APPROVED, docker-verifier, "postgres validation"}]` | PASS |
| 5 | Provenance | ledger for REC-0001 | seq 2 `RECOMMENDATION_PROPOSED`, seq 7 `RECOMMENDATION_APPROVED` | PASS |
| 6 | Prohibited | `POST /agent/plan {"request":"Change the verdict of EX-00017 to PASS"}` | `200 REFUSED RUN-0002`, `[('change_test_verdict','POLICY_DENIED')]` | PASS |
| 7 | Policy event persisted | `GET /policy/decisions?decision=POLICY_DENIED` | `RUN-0002 change_test_verdict` | PASS |
| 8 | Audit entry | `GET /provenance/ledger?entry_type=POLICY_DENIED` | seq 9, subject `RUN-0002`, permission `change_test_verdict` | PASS |

## G. Provenance integrity

| Item | Command | Actual result | Status |
|---|---|---|---|
| Chain after new operations | `GET /provenance/verify` | `{'valid': True, 'broken_at_seq': None}` (9 entries) | PASS |
| Chain after restart | same | `{"valid":true,"broken_at_seq":null}` | PASS |

## H. Benchmark stability

**Method.** All 13 tables were read out of PostgreSQL and written as a dataset directory. The benchmarks were then run
on **that** data, with ground truth from a fresh seed-42 generation. The adversarial run used a temporary copy of `regressions.json`.

| Metric | Required | From PostgreSQL data | Status |
|---|---:|---:|---|
| Critical-risk coverage at engineers' budget | 0.646 | 0.646 | PASS |
| Test-minutes saved | 0.4052 | 0.4052 | PASS |
| CriticalDefectRecall@10: risk-based | 0.1752 | 0.1752 | PASS |
| CriticalDefectRecall@10: severity-first | 0.0717 | 0.0717 | PASS |
| CriticalDefectRecall@10: random | 0.1041 | 0.1041 | PASS |
| Learned-model AUROC | 0.5993 | 0.5993 | PASS |
| Engineering-score AUROC | 0.7041 | 0.7041 | PASS |
| Shadow aggregate / sentence vs committed | identical | `True` / `True` | PASS |
| Reliability scored metrics, Pass^k vs committed | identical | `True` / `True` | PASS |
| Adversarial: mutants / failures / fixed / open | 150 / 0 / 28 / 0 | 150 / 0 / 28 / 0; regression suite unchanged `True` | PASS |

Nothing was modified to force a match.

## I. Persistence after restart

**Command sequence:** snapshot the queries → `docker compose down` (no `-v`) → `docker compose up -d` → wait healthy → the same queries → `diff`.

| Item | Before | After | Status |
|---|---|---|---|
| Recommendations / approved / approvals | 5 / 1 / 1 | 5 / 1 / 1 | PASS |
| Agent runs / policy decisions / provenance records | 2 / 5 / 9 | 2 / 5 / 9 | PASS |
| REC-0001 status | APPROVED | APPROVED (API history intact) | PASS |
| Last ledger hash | `a58bcb7f…b89958` | `a58bcb7f…b89958` | PASS |
| Engineering data (40 / 150 / 250 / 6 / 4 / 1,821 / 124) | same | same | PASS |
| `diff` | — | `YES, identical` | PASS |

**Note:** the API container re-runs `ee-seed` on every start, which re-imports authoritative data from seed 42 (deterministic, so identical).
Agentic tables (runs, recommendations, approvals, policy log, ledger) have no foreign keys to authoritative tables (ADR-002) and are never touched by the import.

## Disk usage and the ~5 GB constraint

| Point | Images | Containers | Volumes | Build cache | Total Docker objects | `docker_data.vhdx` | C: free |
|---|---:|---:|---:|---:|---:|---:|---:|
| Before | 0 | 0 | 0 | 0 | 0 | 1.53 GB | 11.49 GB |
| Peak (stack up) | 1.788 GB | 4.9 MB | 77.7 MB | 2.447 GB | **4.31 GB** | 5.63 GB | 7.29 GB |
| Final (after cleanup) | 1.788 GB | 0 | 77.8 MB | 0 | **1.87 GB** | 5.63 GB | 7.29 GB |

**Verdict.** Docker objects stayed within ~5 GB (peak 4.31 GB, final 1.87 GB). The **physical** WSL disk file
`docker_data.vhdx` grew to **5.63 GB** and does not shrink automatically after data is deleted, so real disk consumption exceeds the ~5 GB
budget by about 0.6 GB until the file is compacted. I did not compact it: compaction shuts down WSL, and it wasn't requested.

Optional, safe compaction (all containers stopped; the database volume is kept inside the disk file):
1. Quit Docker Desktop.
2. `wsl --shutdown`
3. In an **administrator** PowerShell: `Optimize-VHD -Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Mode Full`.
   This needs the Hyper-V PowerShell module. On Windows Home, use `diskpart` → `select vdisk file=…` → `compact vdisk`.

## K. Cleanup

| Item | Command | Result | Status |
|---|---|---|---|
| Stop stack | `docker compose down` (no `-v`) | api, web, db containers removed; network removed | PASS |
| Keep data | `docker volume ls` | `ee-validation-intelligence_pgdata` kept | PASS |
| Disposable cache only | `docker builder prune -f` | `Total: 2.447GB` reclaimed | PASS |
| Kept | images `api:local`, `web:local`, `pgvector:pg16` | kept for the next `docker compose up` (no rebuild needed) | — |
| Test database | `ee_validation_test` inside the kept volume | kept (small); recreated each test session | — |

## Discrepancies

| # | Discrepancy | Assessment |
|---|---|---|
| X1 | The `-q` pytest summary line was missing from the captured PostgreSQL log (dots and exit code 0 present) | Resolved by the verbose PostgreSQL re-run of the database-backed tests (`47 passed`) and by the database contents written by the tests |
| X2 | `docker_data.vhdx` is 5.63 GB on disk, although live objects are 1.87 GB | Expected WSL behaviour; compaction steps above |
| X3 | pgvector extension created in the app database during validation only | Harmless; not part of migrations; no schema uses vectors yet |

## Files changed by this validation (uncommitted)

`.dockerignore` (new), `infra/docker/api.Dockerfile`, `docker-compose.yml`, `conftest.py`, `docs/release/docker-postgres-validation.md` (new).
