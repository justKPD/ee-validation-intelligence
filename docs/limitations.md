# Limitations

This is a research prototype for a portfolio. It is **not** a production automotive validation system, and its
results say nothing about any real organisation's processes, including the BMW Group's.

## Data and validity

- **Synthetic data only.** Every component, requirement, test, execution and defect is generated. Results
  describe behaviour against the generator's fault model ([synthetic-data.md](methodology/synthetic-data.md)), not against real E/E programmes.
- **The counterfactual oracle exists only because the data is synthetic.** With real data, the harness would need
  interventional studies (for example, A/B test campaigns) instead of hidden ground truth.
- **Small evaluation units.** Six builds per seed give five decision points. Bootstrap intervals over five builds are
  wide; the calibration report shows the risk-based vs. engineer difference in critical recall is not distinguishable from zero.
- **One held-out seed.** Tuning uses development seeds 1–3; the held-out comparison uses seed 42 only.
- **Nominal durations.** Benchmarks use nominal test durations for every strategy.

## Engines and ranking

- Risk weights and ranking penalties are expert defaults. The dev-seed tuned configuration is kept separate and is
  not the default; it traded critical recall at K=20 for test-minutes saved.
- The learned defect model is weaker than the engineering score on observed executions; the hybrid adds little.
- Failure fingerprinting is exact-match. Semantic clustering (embeddings) is not implemented.

## Agent

- **Rule-based interpretation** by design (ADR-006). It handles the phrasings covered by tests and the adversarial
  mutators; new phrasings (other languages, split instructions, synonyms) may be misread. After the fixes, the adversarial
  search finding no failures means that mutator set is exhausted, not that the agent is robust in general.
- With `EE_MODEL_PROVIDER=anthropic` only explanations come from the model, and they are grounding-checked by id.
  The model provider path is covered by fake-client tests, not live calls (no credentials were available).
- Tools are MCP-compatible descriptors; a standalone MCP server process is not shipped.

## Security and operations

- **No authentication or authorisation on the API.** The reviewer name on approvals is self-declared. A real
  deployment needs SSO, role-based approval rights, and separation between requester and approver.
- The ledger is tamper-evident (hash chain), not tamper-proof. A privileged database user could rewrite the whole chain;
  anchoring hashes externally (for example, periodic export to write-once storage) would address that.
- Local development defaults to SQLite. The Docker stack runs on PostgreSQL 16 + pgvector, and the same integration
  tests run on PostgreSQL when `EE_TEST_DATABASE_URL` names a dedicated `*_test` database.

## Docker / PostgreSQL validation (completed 2026-09-17)

Validated locally on Docker Desktop (engine 29.8.0). Full evidence: [docker-postgres-validation.md](release/docker-postgres-validation.md).

- **Stack:** `docker compose up --build` brought the database, API and web containers to healthy.
- **Database:** PostgreSQL 16.15 validated from an empty database. pgvector 0.8.6 installed and tested (L2/cosine distance and nearest-neighbour ordering).
- **Migrations:** Alembic `0001 -> 0002` succeeded, creating 18 tables and 20 foreign keys.
- **Seed-42 data matched exactly:** 40 components/ECUs, 150 requirements, 250 tests, 6 builds, 4 variants, 1,821 executions, 124 defects.
  All 13 seeded tables matched the source dataset record for record.
- **Tests:** 188 tests passed against PostgreSQL. The 47 database-backed tests were separately re-run on PostgreSQL and passed.
  The standard SQLite path still passes 188 tests. ruff and mypy pass.
- **UI:** all 8 routes returned 200 and rendered real PostgreSQL-backed data with no console errors.
- **Agent flows:** planner, approval, provenance and `POLICY_DENIED` validated against the containers. The provenance hash chain stayed valid, and all state persisted across a Docker restart.
- **Benchmarks:** stable seed-42 metrics unchanged when recomputed from data read back out of PostgreSQL:
  - critical-risk coverage at the engineers' budget: 0.646
  - test-minutes saved: 0.4052
  - CriticalDefectRecall@10: 0.1752 risk-based, 0.0717 severity-first, 0.1041 random
  - AUROC: 0.5993 learned model, 0.7041 engineering score
  - reliability metrics unchanged
  - adversarial: 150 mutants / 0 failures / 28 fixed regressions

Infrastructure defects found and fixed during that validation:
- missing `.dockerignore`
- `uv` version mismatch between the API image and `uv.lock`
- API startup via `uv run` instead of the installed entry points
- missing health checks
- the local checkout folder name leaking into Docker resource names (fixed with an explicit Compose project name)
- no PostgreSQL test support (added `EE_TEST_DATABASE_URL`)

**Operational limitation (not a correctness issue):** after cleanup, live Docker objects use about 1.87 GB. Docker's WSL
disk file `docker_data.vhdx` stays around 5.63 GB, because it does not shrink automatically. Compacting it is optional and separate
from application correctness.

## What was not executed in this build environment

| Item | Status |
|---|---|
| GitHub Actions | authored; no remote repository was configured, so CI has not run |
| Terraform / AWS | authored; no Terraform binary or AWS credentials, so not validated or applied, and no deployed URL exists |
| Live Claude calls | not made; adapter tested with a fake client |
