# ADR-007 — Public deployment platform: Railway (API + PostgreSQL/pgvector) and Vercel (web)

Status: Accepted (2026-09-17)

## Context
The portfolio release needs a public, HTTPS, always-available demo that preserves the verified architecture:
Next.js web app, FastAPI backend, PostgreSQL 16 + pgvector, persistent agent runs, approvals, policy decisions and
provenance.

The repository already contains an AWS target (`infra/aws`: VPC, ALB, ECS Fargate `api` and `web`, RDS
PostgreSQL 16, Secrets Manager, S3, CloudWatch). Its `terraform fmt -check` and `terraform validate` pass in GitHub
Actions. Before applying it, the pre-deployment audit estimated its recurring cost in eu-central-1 at list prices:

| Resource | Estimate per month |
|---|---|
| Application Load Balancer (running around the clock) | ~$22 |
| ECS Fargate `api` (0.5 vCPU, 1 GB) | ~$21 |
| ECS Fargate `web` (0.25 vCPU, 0.5 GB) | ~$10 |
| RDS PostgreSQL db.t4g.micro + 20 GB storage | ~$16 |
| Public IPv4 addresses (load balancer and tasks) | ~$15 |
| Secrets Manager, CloudWatch Logs, ECR, S3 | ~$2 |
| **Total** | **~$85, and still no HTTPS** (needs a domain + ACM, or CloudFront) |

That is unnecessary recurring cost for a synthetic-data portfolio demo with little traffic.

## Decision
Deploy the public portfolio release on:

- **Railway (Hobby plan):** two services in one project.
  - `api`: FastAPI, built from `infra/docker/api.Dockerfile` (the same image validated with Docker Compose), deployed
    from the GitHub repository's `main` branch, public HTTPS Railway domain, health check `/health`.
  - `postgres`: `pgvector/pgvector:pg16` (the image validated locally), with a persistent Railway volume. It has
    **no public TCP proxy**; the API reaches it only over Railway private networking
    (`postgres.railway.internal`). The database URL is a Railway variable reference; no password is committed.
- **Vercel (Hobby):** `apps/web` (Next.js), GitHub-connected, automatic HTTPS. The only build-time variable is
  `NEXT_PUBLIC_API_URL` (the public API URL, not a secret).
- **AWS/Terraform stays in the repository** as an alternative infrastructure target, validated in CI
  (`fmt`/`validate`) but **not applied** for this release.

Cost controls on Railway:
- No Redis, workers, cron services or duplicate databases.
- The web app runs on Vercel, not Railway.
- OpenTelemetry console export is off (`EE_OTEL_EXPORTER=none`), so logs stay small.
- Serverless sleeping is **not** enabled for the API. Every start migrates, reseeds and verifies the database,
  which takes tens of seconds, so a sleeping API would give recruiters a slow or failed first page load for
  roughly $1–2 per month of savings. Sleeping is also not suitable for the database.

## Consequences
- The recurring cost fits inside the Railway Hobby plan's included usage (measured: API ~180 MB RAM idle,
  PostgreSQL ~35 MB, volume ~0.2 GB; see `docs/release/production-deployment-validation.md`). Vercel Hobby is free.
- The deployed stack keeps the verified PostgreSQL 16.15 + pgvector 0.8.6 database, Alembic migrations and seed-42
  dataset. Each API start runs `scripts/verify_deployment_db.py`, which proves pgvector, the seed counts and the
  provenance hash chain in the deploy log without exposing the database.
- This release does not demonstrate ECS, RDS or ALB operations. Those remain authored and CI-validated Terraform.
- Railway and Vercel are hosting choices for an independent portfolio project. They are not, and do not represent,
  any automotive manufacturer's infrastructure.
- Railway is deprecating `railway.toml` config-as-code (support ends 2026-12-01), and it currently applies only
  the build section. The Dockerfile path is also set as the service variable `RAILWAY_DOCKERFILE_PATH`, and the
  health check is configured in the service settings, so the deployment keeps working after the file stops being read.
