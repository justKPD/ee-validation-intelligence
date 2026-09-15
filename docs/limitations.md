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
- Local development uses SQLite. PostgreSQL is used in Docker and CI configuration.

## What was not executed in this build environment

| Item | Status |
|---|---|
| Docker images and `docker compose up` | authored; Docker was not installed on the build machine |
| GitHub Actions | authored; no remote repository was configured, so CI has not run |
| Terraform / AWS | authored; no Terraform binary or AWS credentials, so not validated or applied, and no deployed URL exists |
| PostgreSQL migrations | run in CI configuration only; locally verified on SQLite |
| Live Claude calls | not made; adapter tested with a fake client |
