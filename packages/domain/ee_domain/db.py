"""Database engine/session factory. `EE_DATABASE_URL` selects Postgres or SQLite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_URL = f"sqlite:///{(REPO_ROOT / 'ee_validation.db').as_posix()}"


def database_url() -> str:
    return os.environ.get("EE_DATABASE_URL", DEFAULT_URL)


def redacted_url(url: str | None = None) -> str:
    """Database URL safe for logs: the password is replaced with ***."""
    return make_url(url or database_url()).render_as_string(hide_password=True)


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    # pre-ping replaces pooled connections that died with a database restart instead of failing the next request
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    return make_engine(url)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    session = session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
