# Threat Model

Scope: API, agent runtime, policy gate, provenance ledger, web UI, and the evaluation harness. Assets:
authoritative validation records, evaluation integrity (benchmarks must not leak), and the audit trail.

| # | Threat | Vector | Mitigation in this codebase | Residual risk / next step |
|---|---|---|---|---|
| T1 | Agent changes engineering truth | model or prompt asks to change verdicts, requirements or tests; close defects; approve releases | no write API for authoritative data (ADR-002, tested); prohibited tools denied by default-deny gate; handlers unreachable | none in-process; real systems need the same boundary at the data-owner service |
| T2 | Prompt injection / role-play override | "ignore previous instructions", "pretend the policy allows everything", obfuscated "cl0se" | injection and intent matching on raw and de-obfuscated text; refusal logs `POLICY_DENIED`; adversarial regression suite | new phrasings; extend mutators, and add model-based intent classification behind the same gate |
| T3 | Premature action on ambiguous requests | missing or unknown build, variant or component | clarification before any plan tool; measured premature-action rate in reliability lab | limited to the parsed slot set |
| T4 | Hallucinated evidence | model cites tests, defects or requirements that don't exist | plans come from engines; model text grounding-checked against fact ids, with offline fallback; lab hallucination metric | semantic (non-id) errors in prose are not detected |
| T5 | Self-approval | agent approves its own recommendation | `approve_recommendation` denied by policy; provenance service rejects the agent actor as reviewer | reviewer identity is self-declared (no authentication) |
| T6 | Audit tampering | editing stored runs, approvals or recommendations | hash-chained ledger; `/provenance/verify` detects any modified or reordered entry (tested) | a privileged user can rebuild the whole chain; anchor hashes externally |
| T7 | Evaluation leakage | engines or models see results of the build being planned | as-of snapshots; `visible_data`; tests tamper future data and require identical outputs; ranking source cannot import ground truth | none known; keep leakage tests mandatory in CI |
| T8 | Benchmark gaming | tuning on the reported seed; hand-edited numbers | tuning only on dev seeds; held-out comparison; every sentence and table generated from runs | single held-out seed |
| T9 | Unauthenticated access / abuse | open API endpoints, POST `/agent/plan` flooding | CORS restricted to configured origins; request size limits on agent input | add authentication, per-user rate limits and WAF before any public deployment |
| T10 | Secret exposure | LLM or database credentials in the repository | credentials only via environment and Secrets Manager (Terraform); no keys in repo; synthetic local DB password only in docker-compose | add secret scanning in CI |
| T11 | Dependency / supply chain | compromised Python or npm packages | lockfiles (`uv.lock`, `package-lock.json`); pinned CI actions by major version | add Dependabot, SBOM and hash pinning |
| T12 | Data exfiltration via model provider | request text and facts sent to an external LLM | offline provider is the default; Anthropic provider only when explicitly enabled; data is synthetic | real data would need a contractual and data-residency review before enabling |
