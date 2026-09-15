# ADR-002 — Authoritative data vs. agent boundary

Status: Accepted (2026-09-15)

## Decision
- Authoritative records: requirements, test definitions, executions/verdicts, defects, builds, variants. They change only through the ETL import path.
- Deterministic engines own all calculated truth (risk, coverage, evidence status, ranking).
- Agents may **read, explain, recommend, propose**. Agents may never modify requirements or test definitions, change verdicts, close defects, approve releases, or silently execute high-risk actions.
- Every agent tool call passes a policy gate. Prohibited calls return `POLICY_DENIED` and are persisted.
- The API exposes no write endpoints for authoritative data. The only writes are recommendation lifecycle, approvals, and the ledger.

## Consequences
LLM mistakes cannot corrupt engineering truth. Recommendations stay auditable.
