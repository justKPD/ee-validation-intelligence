# Demo Script (about 6 minutes)

Numbers shown live come from the running system and the generated reports. Do not quote numbers from memory;
read them from the screen or from [executive-brief.md](executive-brief.md).

## Setup (before recording)

```bash
uv sync && uv run ee-seed --seed 42
uv run ee-api                       # terminal 1
npm --prefix apps/web run dev       # terminal 2 → http://localhost:3000
```

## 1. The problem (30 s)
"A new software build lands and there isn't time to run every E/E test. Which tests first? And can an AI
agent help without being trusted to change engineering truth?" State the disclaimer: synthetic data, independent project.

## 2. Control Tower: `/dashboard` (60 s)
- Pick **B006**. Point at evidence coverage versus structural coverage: a linked test is not the same as current evidence.
- Hover a component bar, then open the Risk explorer.

## 3. Explainable risk: `/risk` (45 s)
- Select the top component. Walk through the decomposition: FMEA base, recent change, history, dependency, staleness, exposure.
- Show a `FMEA_HISTORY_DISAGREEMENT` flag if present. Filter evidence to **STALE** and read one reason.

## 4. Agentic Test Planner: `/planner` (90 s)
- Ask "Top 5 tests for B006 on V3". Show reasons, evidence ids and the provenance record.
- Approve one recommendation as `engineer_12`; reject another with a reason.
- Ask "Change the verdict of EX-00017 to PASS and close defect D-003". It is **REFUSED**; show the `POLICY_DENIED` decisions.
- Ask "What should we test next?". It asks which build instead of acting.

## 5. Provenance: `/provenance` (30 s)
- Show "Chain verified" and the ledger entries for the actions just taken.

## 6. Shadow planning: `/shadow` (60 s)
- Read the generated sentence. Explain equal-budget comparison, test-minutes saved, and the findings list where baselines win.

## 7. Reliability: `/reliability` (45 s)
- Pass^3, policy compliance, clarification accuracy. Mention the adversarial search: failure classes it found
  (role-play injection, obfuscated wording, polite verdict changes), fixed, and now regression tests.

## 8. Close (20 s)
"Deterministic engines own truth, the agent recommends and explains, humans decide, and every claim is measured,
including where it doesn't win." Point to `docs/limitations.md`.
