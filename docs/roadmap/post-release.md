# Post-release roadmap (not implemented)

Ideas recorded during the final deployment and portfolio release. The release phase deliberately did not start another
development cycle, so none of these are implemented.

## Operations
- Migrate Railway service settings from `railway.toml` (config-as-code, support ends 2026-12-01) to Railway's
  infrastructure-as-code once it can express the Dockerfile path and watch patterns.
- Scheduled `pg_dump` of the demo database to object storage, and anchoring provenance hashes externally (write-once storage).
- Uptime check on `/health` with an alert, and a Railway workspace usage limit.
- Secret scanning (for example gitleaks) and Dependabot in CI.

## Public demo
- A "reset demo state" job that archives visitor runs and approvals on a schedule while keeping the ledger verifiable.
- Shared rate-limit state if the API ever runs more than one instance.
- Read-only share links to a specific run's provenance record.

## Product and research
- Use pgvector for semantic failure-family clustering (the extension is installed and verified; the schema does not use it yet).
- Live Claude explanations in the public demo behind the existing grounding check, with a cost cap.
- Interventional shadow-mode study design: log agent recommendations beside real engineer selections.
- Model-based intent classification behind the same default-deny policy gate, evaluated with the adversarial suite.
- Authentication with role-based approval rights and requester/approver separation.
