# ADR-006 — Agent runtime: deterministic planning, LLM explanation, provider-agnostic adapter

Status: Accepted (2026-09-15)

## Context
Agents that pick actions from free text act prematurely on ambiguous requests, violate policies, and invent
facts. The platform needs an agent whose recommendations are auditable and repeatable, and that stays useful
without any LLM credentials.

## Decision
- **Orchestration:** a LangGraph `StateGraph` with the nodes `interpret → (refuse | clarify | gather → plan → explain)`.
- **Deterministic interpretation** of slots (build, variant, component, budget, top-N), prohibited intents and
  injection attempts. The agent asks instead of acting when the build or variant is missing, unknown or ambiguous.
- **Tools** live in an MCP-compatible registry (`name`, `description`, `inputSchema`, permission annotation). Every
  call passes the default-deny `PolicyGate`; prohibited tools are registered so that attempts are denied and logged as
  `POLICY_DENIED`, but their handlers are unreachable.
- **Plans come from the engines, not the model.** The ranking engine selects tests; the model only writes the explanation.
- **Model adapter:** `OfflineProvider` (deterministic, default) or `AnthropicProvider` (`EE_MODEL_PROVIDER=anthropic`,
  model `claude-opus-5` by default, server-side refusal fallbacks enabled). Model text is **grounding-checked**: if it
  cites any id absent from the facts, it is discarded and the offline explanation is used, and the run records
  `grounded=false`.
- **Persistence:** every run, policy decision and proposed recommendation is written through `ProvenanceService` to a
  hash-chained ledger ([ADR-002](ADR-002-authority-boundary.md)).

## Consequences
Plans are reproducible (Pass^k is measurable), prohibited actions are structurally impossible, and hallucinated
references cannot reach engineers. The trade-off: natural-language understanding is limited to the supported
request patterns. Phase 10's adversarial generator probes exactly that boundary.
