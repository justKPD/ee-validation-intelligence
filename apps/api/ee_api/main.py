from __future__ import annotations

import os

from ee_domain.db import get_engine
from ee_domain.telemetry import configure_tracing
from fastapi import FastAPI
from sqlalchemy import Engine, text

from ee_api.routes import catalog, intelligence

DISCLAIMER = (
    "Independent portfolio project using entirely synthetic data. "
    "Not affiliated with, and does not represent, any BMW Group system."
)


def create_app(engine: Engine | None = None) -> FastAPI:
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

    app.state.snapshots = {}  # build_id -> ValidationSnapshot; authoritative data changes only via ETL
    app.include_router(catalog.router)
    app.include_router(intelligence.router)

    configure_tracing("ee-api")
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    return app


def run() -> None:
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("EE_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("EE_API_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
