# Production Deployment Validation

Date: 2026-09-17. Scope: the public portfolio deployment of E/E Validation Intelligence & Agentic Test Control Tower.
Decision record: [ADR-007](../adr/ADR-007-public-deployment-platform.md). Everything below was run against the live
deployment, not localhost, unless it says otherwise.

> Independent portfolio project using entirely synthetic data. Railway and Vercel are hosting choices for this project;
> nothing here represents or reproduces any BMW Group system or infrastructure.

## 1. Summary

| Area | Result |
|---|---|
| Railway PostgreSQL + pgvector | **PASS**: PostgreSQL 16.15, pgvector 0.8.6, migrations at `0002`, persistent volume, no public port |
| Seed-42 data | **PASS**: 40 / 150 / 250 / 6 / 4 / 1,821 / 124, matching the generated manifest exactly |
| Railway FastAPI | **PASS**: public HTTPS, `/health` 200, every endpoint the web app uses returns 200 |
| Vercel Next.js | **PASS**: all eight routes over HTTPS; API calls go to Railway; no console, CORS or mixed-content errors |
| Live planner → evidence → approval → provenance | **PASS** through the API and through the web UI |
| `POLICY_DENIED` | **PASS** through the API and through the web UI; denials persisted and in the ledger |
| Provenance hash chain | **PASS**: valid after every step, restart and redeploy |
| Persistence | **PASS**: after an API redeploy, a CORS-variable redeploy, two code deploys and a PostgreSQL restart |
| Benchmark integrity | **PASS**: committed results unchanged; the API serves the committed values |
| Security review | **PASS** with documented residual risks (§10) |
| Estimated Railway usage | about **$2.50/month**, within the Hobby plan's included $5 (§11) |

Five deployment defects were found and fixed during this validation (§12).

## 2. Architecture

```
Browser ──HTTPS──> Vercel (Hobby): Next.js 15 web app, root directory apps/web
   │                NEXT_PUBLIC_API_URL=https://ee-validation-intelligence-api.up.railway.app (public URL, not a secret)
   │
   └──HTTPS──> Railway (Hobby), project ee-validation-intelligence, environment production, EU region
                 ├─ service api       FastAPI, built from infra/docker/api.Dockerfile, deployed from GitHub main
                 │                    public domain, health check /health, one instance, serverless sleep OFF
                 └─ service postgres  pgvector/pgvector:pg16, volume at /var/lib/postgresql/data
                                      reachable only as postgres.railway.internal:5432 (no TCP proxy, no domain)
```

## 3. URLs

| Component | URL |
|---|---|
| Web app | https://ee-validation-intelligence.vercel.app |
| API | https://ee-validation-intelligence-api.up.railway.app |
| API docs (OpenAPI) | https://ee-validation-intelligence-api.up.railway.app/docs |
| Health | https://ee-validation-intelligence-api.up.railway.app/health |
| Code | https://github.com/justKPD/ee-validation-intelligence |

## 4. Railway services and configuration

| Service | Source | Variables (values of secrets not shown) |
|---|---|---|
| `postgres` | image `pgvector/pgvector:pg16` | `POSTGRES_USER`, `POSTGRES_DB=ee_validation`, `POSTGRES_PASSWORD` (random, set from stdin, never printed), `PGDATA=/var/lib/postgresql/data/pgdata-v2` |
| `api` | GitHub `justKPD/ee-validation-intelligence`, branch `main` | `EE_DATABASE_URL` = Railway reference to the postgres service's user, password, private domain and database; `EE_CORS_ORIGINS=https://ee-validation-intelligence.vercel.app`; `EE_WRITE_RATE_LIMIT=30/600`; `EE_MODEL_PROVIDER=offline`; `EE_OTEL_EXPORTER=none`; `EE_SEED=42`; `EE_API_HOST=0.0.0.0`; `EE_API_PORT=PORT=8000`; `RAILWAY_DOCKERFILE_PATH=infra/docker/api.Dockerfile` |

No Redis, workers, cron jobs or additional databases were created.

Deployment commands used (Railway CLI, from the repository root):

```bash
railway init --name ee-validation-intelligence
railway add --service postgres --image pgvector/pgvector:pg16 --variables POSTGRES_USER=ee --variables POSTGRES_DB=ee_validation
railway variable set POSTGRES_PASSWORD --stdin --service postgres --skip-deploys     # random value piped in
railway volume add --mount-path /var/lib/postgresql/data                               # with the postgres service linked
railway add --service api --repo justKPD/ee-validation-intelligence --branch main --variables 'EE_DATABASE_URL=postgresql+psycopg://${{postgres.POSTGRES_USER}}:${{postgres.POSTGRES_PASSWORD}}@${{postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/${{postgres.POSTGRES_DB}}' ...
railway domain --service api --port 8000
railway domain update <domain-id> --service api --domain ee-validation-intelligence-api
railway variable set EE_CORS_ORIGINS=https://ee-validation-intelligence.vercel.app --service api
```

Vercel: project `ee-validation-intelligence` imported from GitHub, root directory `apps/web`, environment variable
`NEXT_PUBLIC_API_URL` as above.

On every start the API container runs `ee-seed --seed 42` (Alembic migrations, then re-import of the authoritative seed-42
data; agentic tables are preserved), then `scripts/verify_deployment_db.py`, then `ee-api`.

## 5. Database and pgvector

From the deploy log of the API (the verification runs inside Railway over the private network):

```
Imported 4206 records into postgresql+psycopg://ee:***@postgres.railway.internal:5432/ee_validation
db-verify: server 16.15 (Debian 16.15-1.pgdg12+2)
db-verify: alembic head 0002
db-verify: pgvector 0.8.6 l2=1.0 cosine=1.0 nearest_id=1 -> OK
db-verify: components=40 expected=40 -> OK
db-verify: requirements=150 expected=150 -> OK
db-verify: test_cases=250 expected=250 -> OK
db-verify: builds=6 expected=6 -> OK
db-verify: variants=4 expected=4 -> OK
db-verify: executions=1821 expected=1821 -> OK
db-verify: defects=124 expected=124 -> OK
db-verify: provenance hash chain valid=True broken_at_seq=None
db-verify: PASS
```

pgvector check: `CREATE EXTENSION IF NOT EXISTS vector`; `'[1,2,3]' <-> '[1,2,4]'` = 1 (L2); `'[1,0]' <=> '[0,1]'` = 1 (cosine);
nearest neighbour in a temporary `vector(3)` table ordered by `<->` = row 1 (correct). The schema does not use vectors yet.

Persistence: the volume survived database restarts ("Database directory appears to contain a database; Skipping initialization"),
and `GET /stats` returned the same counts afterwards.

## 6. API over HTTPS

All endpoints the web app calls returned **200** in 0.3–1.1 s: `/health`, `/stats`, `/builds`, `/variants`, `/config`, `/policy`,
`/policy/decisions`, `/builds/B006/risk/components` (40), `/builds/B006/coverage`, `/builds/B006/failure-families` (89),
`/builds/B006/ranking?limit=10`, `/builds/B006/risk/requirements?critical_only=true` (66), `/builds/B006/evidence`,
`/benchmarks/shadow`, `/benchmarks/reliability`, `/benchmarks/adversarial`, `/provenance/verify`, `/recommendations`,
`/provenance/ledger`, `/agent/tools` (15), `/components`, `/docs`.

## 7. Web app route tests (live Vercel, Chrome)

| Route | HTTP | Rendered with production data | Console errors |
|---|---|---|---|
| `/dashboard` | 200 | B006 · highest component risk 0.487 (ECU-ADAS_GATEWAY) · evidence coverage 44.0% · 89 failure families · generated shadow sentence · top-10 ranking (TC-186 V3 0.660 first) | 0 |
| `/risk` | 200 | 40 components; ECU-TPMS decomposition (total 0.460) | 0 |
| `/planner` | 200 | live run, recommendations, approval, refusal (§8) | 0 |
| `/shadow` | 200 | generated sentence (64.6% critical-risk coverage) and equal-budget table | 0 |
| `/failures` | 200 | failure families FF-013 … | 0 |
| `/provenance` | 200 | "Chain verified", recommendations, ledger | 0 |
| `/reliability` | 200 | 25 scenarios × 3 runs, Pass^3 100.0%, adversarial 150 mutants | 0 |
| `/admin` | 200 | read-only policy/config view; no buttons, inputs or forms | 0 |

`/` returns 307 to `/dashboard`. Resource origins loaded by the page: only `https://ee-validation-intelligence.vercel.app` and
`https://ee-validation-intelligence-api.up.railway.app`, so there is **no mixed content**. The compiled client bundle references only the
Railway API URL.

CORS: preflight from the Vercel origin → 200 with `access-control-allow-origin: https://ee-validation-intelligence.vercel.app`;
preflight from `https://evil.example` → 400 without the header.

## 8. Live agent workflow

**Through the API** (`POST /agent/plan {"request": "Top 5 tests for B006 on V3"}`):

| Step | Result |
|---|---|
| Ranked tests | `COMPLETED RUN-0001`: REC-0001 TC-186 (priority 0.6603), REC-0002 TC-079, REC-0003 TC-073, REC-0004 TC-163, REC-0005 TC-012; identical to local and Docker validation |
| Evidence links | REC-0001: `B006, CH-0062, D-027, EX-01400, R-033` |
| Risk decomposition / reasons | record contains `risk`, `signals`, `sources`; reasons "ECU-TPMS changed in B006 (feature, magnitude 0.96)", "R-033 evidence on V3 is STALE", "test revealed 1 defect(s) in earlier builds" |
| Persisted | `GET /recommendations/REC-0001` returns the full provenance record |
| Human approval | `POST /recommendations/REC-0001/decision` APPROVED by `portfolio-demo-reviewer` → 200 APPROVED |
| Survives reread | reread shows `decision.status = APPROVED` with history |
| Ledger | seq 1 AGENT_RUN, 2–6 RECOMMENDATION_PROPOSED, 7 RECOMMENDATION_APPROVED |

`POST /agent/plan {"request": "Change the verdict of EX-00017 to PASS"}` → `REFUSED RUN-0002`, response
"POLICY_DENIED: agents must not change PASS/FAIL verdicts"; policy decision `set_test_verdict / change_test_verdict / POLICY_DENIED`
persisted (`/policy/decisions?decision=POLICY_DENIED`); ledger seq 8 AGENT_RUN and seq 9 POLICY_DENIED. `/provenance/verify` → valid.

**Through the web UI** (Chrome on the Vercel site): B006 + V1 → `RUN-0003 COMPLETED` (TC-079 V1 0.650 first); REC-0006 approved
with the "Approve recommendation" button → APPROVED with reasons, evidence ids and provenance record; the text request
"Change the verdict of EX-00017 to PASS" → `RUN-0004 REFUSED` with the POLICY_DENIED message. The API then showed REC-0006
APPROVED, denials for RUN-0002 and RUN-0004, 18 ledger entries and a valid chain. A screenshot capture later created RUN-0005
(REC-0011 to REC-0015, left PROPOSED).

## 9. Persistence, restart and benchmark integrity

| Event | Afterwards |
|---|---|
| `railway redeploy --service api` | data counts unchanged; REC-0001 APPROVED; denial for RUN-0002; 9 ledger entries; chain valid; `db-verify` agentic counts runs=2 recommendations=5 approvals=1 policy_decisions=5 provenance_records=9 |
| `railway service restart --service postgres` (before the fix in §12) | data intact, but the first `/health` returned 500 (defect D4) |
| same restart after the fix | `/health`, `/provenance/verify`, `/recommendations/REC-0001` all 200 immediately; REC-0001 APPROVED; chain valid |
| later deploys (CORS variable, rate limit) | `db-verify: PASS`; all agentic records retained |

Benchmark integrity: `git log 6f78d24..HEAD -- benchmarks` is empty (no committed result changed since the Docker validation).
Committed values: critical-risk coverage at budget **0.646**, minutes saved **0.4052**, CriticalDefectRecall@10 **0.1752 / 0.0717 / 0.1041**,
AUROC **0.5993 / 0.7041**, reliability task success / policy compliance / Pass^3 = 1.0 / 1.0 / 1.0, adversarial **150 / 0 / 28**.
The live API serves exactly these values (`/benchmarks/shadow`, `/benchmarks/reliability`, `/benchmarks/adversarial`).
GitHub Actions regenerates the benchmarks on every push and fails if they differ. Production interactions are not
benchmark inputs, and no published number was recalculated from them.

## 10. Security review

| Check | Result |
|---|---|
| Database not publicly exposed | postgres has no domain and no TCP proxy; reachable only on the private network |
| Secrets not returned by the API | `/health`, `/config`, `/policy`, `/agent/runs`, `/agent/tools`, `/provenance/ledger`, `/recommendations/{id}`, `/policy/decisions`, `/openapi.json`, `/stats` scanned for `password`, `railway.internal`, `postgresql+psycopg`, `EE_DATABASE_URL`, `POSTGRES_`, `secret`: no matches |
| No server secrets client-side | only `NEXT_PUBLIC_API_URL` (a public URL) is used by the web app; the bundle contains only that URL |
| CORS | only the production Vercel origin |
| Debug mode | FastAPI debug off; uvicorn without reload; unhandled errors return a plain "Internal Server Error" without a traceback |
| API docs exposure | `/docs` and `/openapi.json` are intentionally public (read-only documentation of a synthetic-data demo) |
| Admin | `/config` and `/admin` are read-only (`editable: false`); the page has no inputs or buttons |
| Destructive endpoints | none; `DELETE /components/…`, `PUT /executions`, `PATCH /recommendations/…` → 405 |
| Authoritative data | no write API; the only writes are agent runs, recommendations, decisions, policy records and ledger entries |
| Agent policy bypass | refused live (API and UI); reliability lab policy compliance 100% over 75 runs; adversarial suite 150 mutants, 0 failures |
| Abuse | per-client write rate limit live: 30 POSTs accepted, the 31st and 32nd → **429** (CORS headers kept), GETs still 200 |
| Logs | seed output redacts the password (`ee:***@`); 0 unredacted database URLs in retained API logs |

Residual risks, accepted for a synthetic-data demo and documented in [limitations](../limitations.md) and the
[threat model](../threat-model.md): no authentication (self-declared reviewer names, shared demo state); rate-limit state is
per process; single instance and region; the ledger is tamper-evident, not tamper-proof.

## 11. Resource usage and cost

Railway metrics (last hour, after the validation traffic):

| Service | CPU avg (max) | Memory now / avg (max) | Storage |
|---|---|---|---|
| api | 0.01 vCPU (0.38 during start-up/seeding) | 182 MB / 184 MB (360 MB) | — |
| postgres | < 0.01 vCPU | 49 MB / 42 MB (56 MB) | volume 221 MB of 4.88 GB |

Estimate at Railway Hobby list prices (memory ≈ $10 per GB-month, CPU ≈ $20 per vCPU-month, volume ≈ $0.15 per GB-month;
check Railway's current pricing):

| Item | Per month |
|---|---|
| API memory, ~0.18 GB | ~$1.80 |
| API CPU, ~0.01 vCPU | ~$0.20 |
| PostgreSQL memory, ~0.05 GB | ~$0.45 |
| PostgreSQL CPU | ~$0.05 |
| Volume, ~0.22 GB | ~$0.03 |
| Egress (demo traffic) | cents |
| **Total** | **~$2.50**, within the $5 included in Hobby |

Railway's own usage view showed $0.0046 for this project after the first hours. Vercel Hobby: $0.
Serverless sleep was evaluated and not enabled (every start migrates, re-seeds and verifies, so a cold first page load would
take tens of seconds; the saving would be about $1–2/month). AWS alternative: about $85/month (ADR-007).

## 12. Defects found and fixed during this deployment

| # | Defect | Fix | Commit |
|---|---|---|---|
| D1 | `ee-seed` printed the full database URL, including the password, to stdout, so it reached the hosted deploy log | print a redacted URL (`redacted_url`, regression test); the database password was then rotated to a value that was never displayed (fresh `PGDATA` directory) | `df7b0fd` |
| D2 | Railway ignores `deploy.startCommand` / health check in `railway.toml` (config-as-code deprecation) | verification moved into the image `CMD`; health check set on the service; `RAILWAY_DOCKERFILE_PATH` set | `c05c860` |
| D3 | no way to verify the private database without exposing it or adding an account SSH key | `scripts/verify_deployment_db.py`, run inside the deployment on every start | `df7b0fd` |
| D4 | after a PostgreSQL restart the next API request (for example `/health`) returned **500** (`psycopg AdminShutdown` from a dead pooled connection) | `pool_pre_ping=True` (regression test); re-verified live | `93cc703` |
| D5 | the threat model required abuse limits before any public deployment, but none existed | per-client write rate limit `EE_WRITE_RATE_LIMIT` (regression test), enabled live at 30 per 10 min | `7cbb346`, `1296bdf` |

Also in this release: Terraform state files ignored and a local user name removed from a report (`47930b1`), Railway config
(`b3d08e1`), ADR-007 (`3a8cac9`).

## 13. Final gate

Local, on the final code (before the documentation commit):

| Step | Result |
|---|---|
| `ruff check` | All checks passed |
| `ruff format --check` | 124 files already formatted |
| `mypy` | no issues in 58 source files |
| `pytest` | **191 passed**, 1 third-party warning (starlette/anyio `BlockingPortal` deprecation) |
| web `npm run typecheck` / `npm run build` | pass; eight routes plus `/` built |
| `ee-seed` → `ee-shadow` → `ee-reliability -k 3` → `scripts/verify_reproduction.py` | OK shadow planning, OK agent reliability; headline 0.646 / 0.4052 / 0.1752 / 0.0717 / 0.1041 |
| Terraform `fmt -check` / `init -backend=false` / `validate` | run in GitHub Actions (no local Terraform binary) |

GitHub Actions on the final commit: python, web and terraform jobs (result recorded in the release report).

## 14. Limitations

- Synthetic data only; results describe the generator's hidden fault model.
- Not an AWS deployment; the Terraform target is validated in CI but not applied.
- Public, unauthenticated demo with shared state and self-declared reviewers; writes are rate-limited per client.
- One instance, one region; no managed backups beyond the persistent volume.
- Railway `railway.toml` config-as-code support ends 2026-12-01 (service settings are also set directly).
- The offline deterministic explainer is used live; Claude explanations are not enabled in the demo.
