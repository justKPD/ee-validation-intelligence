# ADR-003 — JD-aligned technology stack

Status: Accepted (2026-09-15)

| Concern | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI |
| Database | PostgreSQL 16 + pgvector (SQLite allowed for local/tests) |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Validation | Pydantic v2 |
| Workspace | uv |
| Quality | pytest, ruff, mypy |
| Frontend | Next.js + TypeScript |
| Agents | LangGraph + LangChain |
| Tools | MCP-compatible tool interfaces (JSON-schema tool registry; MCP server adapter) |
| ML | scikit-learn; LightGBM/XGBoost where appropriate |
| Containers / CI | Docker, GitHub Actions |
| Observability | OpenTelemetry |
| Deployment target | AWS (ECS/Fargate, RDS, S3, CloudWatch) |
| Models | provider-agnostic adapter (offline deterministic, Anthropic, OpenAI, Bedrock) |

Libraries for later phases are locked here even when not yet used.
