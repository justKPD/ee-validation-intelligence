# Recruiter Summary

> Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research. Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.

**One line:** a working platform that decides which automotive electronics tests to run first, lets an AI agent explain
and propose, but never decide, and proves both with reproducible benchmarks.

- **Problem:** limited test time per software build; which tests matter most?
- **Built:** data pipeline, risk and coverage engines, test ranking, policy-gated AI agent with human approval and audit
  ledger, evaluation lab, web control tower, deployment configuration.
- **Evidence:** at the same test budget as the simulated engineers, the ranker covered 64.6%
  of critical risk (engineers 49.3%) and needed 40.5% fewer test-minutes to find as many hidden defects.
  The agent never violated its policy across 75 repeated evaluation runs.
- **Honesty:** results are on synthetic data; limitations are documented in the repository.
- **Stack:** Python, FastAPI, PostgreSQL, scikit-learn, LangGraph, MCP-style tools, Next.js, Docker, GitHub Actions, Terraform/AWS.

Generated from benchmark results at commit `ef7f162` by `scripts/build_brief.py`. Seed 42.
