from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path

from ee_domain.db import REPO_ROOT, get_engine
from ee_domain.telemetry import configure_tracing
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text

from ee_api.routes import admin, agent, catalog, intelligence, ranking, reliability

DISCLAIMER = (
    "Independent portfolio project using entirely synthetic data. "
    "Not affiliated with, and does not represent, any BMW Group system."
)


def create_app(engine: Engine | None = None, benchmark_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="E/E Validation Intelligence API",
        version="0.1.0",
        description=f"Risk-based E/E validation intelligence. {DISCLAIMER}",
    )
    app.state.engine = engine or get_engine()

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        with app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "disclaimer": DISCLAIMER}

    # per-process caches; authoritative data changes only through the ETL import
    app.state.snapshots = {}
    app.state.contexts = {}
    app.state.rankings = {}
    app.state.models = {}
    app.state.dataset_view = None
    app.state.agent = None
    app.state.reliability_dir = REPO_ROOT / "benchmarks" / "agent-reliability" / "results"
    app.state.benchmark_dir = benchmark_dir or REPO_ROOT / "benchmarks" / "shadow-planning" / "results"
    app.include_router(catalog.router)
    app.include_router(intelligence.router)
    app.include_router(ranking.router)
    app.include_router(agent.router)
    app.include_router(reliability.router)
    app.include_router(admin.router)
    write_limit = _parse_rate_limit(os.environ.get("EE_WRITE_RATE_LIMIT", ""))
    if write_limit is not None:
        max_writes, window_s = write_limit
        recent: dict[str, deque[float]] = defaultdict(deque)

        # public demo guard: the only writes are agent runs and decisions; cap them per client so the demo
        # database cannot be flooded. Registered before CORS so 429 responses still carry CORS headers.
        @app.middleware("http")
        async def limit_writes(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.method == "POST":
                client = _client_key(request)
                now = time.monotonic()
                hits = recent[client]
                while hits and now - hits[0] > window_s:
                    hits.popleft()
                if len(hits) >= max_writes:
                    return JSONResponse(
                        {
                            "detail": f"Demo write limit reached ({max_writes} per {window_s}s). Try again shortly."
                        },
                        status_code=429,
                    )
                hits.append(now)
            return await call_next(request)

    origins = os.environ.get("EE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    configure_tracing("ee-api")
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    return app


def _client_key(request: Request) -> str:
    """The visitor behind a request, for the write limit.

    Through the web app's same-origin proxy the request comes from Vercel, which passes the visitor's address in
    ``x-vercel-forwarded-for``; a direct call carries the platform edge's ``x-real-ip``. This is a courtesy guard
    against casual flooding, not a security boundary: a direct caller can set either header.
    """
    for header in ("x-vercel-forwarded-for", "x-real-ip"):
        if value := request.headers.get(header):
            return value.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _parse_rate_limit(spec: str) -> tuple[int, int] | None:
    """`EE_WRITE_RATE_LIMIT="30/600"` allows 30 POST requests per client per 600 s; empty disables the limit."""
    if not spec.strip():
        return None
    count, _, window = spec.partition("/")
    return int(count), int(window)


def run() -> None:
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("EE_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("EE_API_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
