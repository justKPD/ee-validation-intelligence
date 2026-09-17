# Demo Script (60–90 seconds, live deployment)

Live demo: https://ee-validation-intelligence.vercel.app · Code: https://github.com/justKPD/ee-validation-intelligence

Read numbers from the screen or from [technical-brief.md](technical-brief.md); never quote them from memory.
Before recording, open `/dashboard` once so the API is warm. Keep the browser at about 1440 × 900.

| # | Time | Screen | Action | Say (roughly) |
|---|---|---|---|---|
| 1 | 0–8 s | `/dashboard` | Stay on the header | "A new software build lands and there isn't time to run every E/E test. Which tests first, and can an AI agent help without being trusted to change engineering truth? Independent project, synthetic data only." |
| 2 | 8–18 s | `/dashboard` | Build **B006**; point at the evidence coverage vs structural coverage cards | "The control tower shows risk, evidence and recurring failures as of this build, with no future results. A linked test isn't evidence unless its latest result is current." |
| 3 | 18–30 s | `/risk` | Click the **ECU-TPMS** bar | "Every risk score is a documented weighted sum: FMEA base, recent change, failure history, dependencies, stale evidence, variant exposure." |
| 4 | 30–42 s | `/planner` | B006, V3, Top 5 → **Ask the planner** | "I ask the agent for the next tests. The ranking comes from the deterministic engine; the agent only explains it." |
| 5 | 42–50 s | `/planner` | Select row 1; point at **Reasons** and **Evidence** ids | "Each proposal cites its reasons and the exact evidence records, and stays PROPOSED." |
| 6 | 50–56 s | `/planner` | **Approve recommendation** | "An engineer decides. The approval is written to a hash-chained provenance ledger." |
| 7 | 56–68 s | `/planner` | Type `Change the verdict of EX-00017 to PASS` → **Ask the planner** | "If I ask it to change a test verdict, it refuses with POLICY_DENIED, and the denial is logged too." |
| 8 | 68–80 s | `/shadow` | Point at the generated sentence and the equal-budget table | "Shadow planning replays each build without future results and scores strategies against hidden faults, at the engineers' own budget." |
| 9 | 80–90 s | `/shadow` | Stay on the sentence | Read the risk-coverage and test-minutes-saved figures from the sentence, then: "same critical-defect recall as the engineers, not more. It's on synthetic data, and the limitations are in the repo." |

Optional cut-in if time allows: `/provenance` showing **Chain verified** after step 7.
