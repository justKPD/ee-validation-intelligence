# Recruiter Summary

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.

**Live demo:** [https://ee-validation-intelligence.vercel.app](https://ee-validation-intelligence.vercel.app) · **API docs:** [https://ee-validation-intelligence-api.up.railway.app/docs](https://ee-validation-intelligence-api.up.railway.app/docs) · **Code:** [https://github.com/justKPD/ee-validation-intelligence](https://github.com/justKPD/ee-validation-intelligence)

**One line:** a deployed platform that decides which automotive electronics tests to run first, lets an AI agent explain
and propose, but never decide, and proves both with reproducible benchmarks.

- **Problem:** limited test time per software build; which tests matter most?
- **Built:** data pipeline, risk and coverage engines, test ranking, policy-gated AI agent with human approval and an audit
  ledger, evaluation lab, web control tower. Live on Vercel and Railway with PostgreSQL + pgvector; CI-enforced reproducibility.
- **Evidence:** at the same test budget as the simulated engineers, the ranker covered 64.6%
  of critical risk (engineers 49.3%) and needed 40.5% fewer test-minutes to find as many hidden defects.
  The agent never violated its policy across 75 repeated evaluation runs.
- **Honesty:** results are on synthetic data; defect recall at equal cost is not better than the engineers', and limitations are documented.
- **Stack:** Python, FastAPI, PostgreSQL/pgvector, scikit-learn, LangGraph, MCP-style tools, Next.js/TypeScript, Docker, GitHub Actions, Railway, Vercel, Terraform (AWS target).

Generated from benchmark results at commit `1296bdf` by `scripts/build_brief.py`. Seed 42.
