"""Shared fixtures: one generated programme + one migrated database per test session.

By default the database is a temporary SQLite file. Set ``EE_TEST_DATABASE_URL`` (for example
``postgresql+psycopg://ee:...@localhost:5432/ee_validation_test``) to run the same integration tests against
PostgreSQL. That database's ``public`` schema is dropped and recreated each session, so it must be a dedicated
test database and never the application database.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from ee_domain.db import make_engine
from ee_etl.importer import load_dataset
from ee_etl.migrate import upgrade_head
from ee_generator import GeneratedProgramme, generate_programme, write_programme
from sqlalchemy import Engine, create_engine, text


@pytest.fixture(scope="session")
def programme() -> GeneratedProgramme:
    return generate_programme(seed=42)


@pytest.fixture(scope="session")
def dataset_dir(programme: GeneratedProgramme, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_programme(programme, tmp_path_factory.mktemp("synthetic"))


@pytest.fixture(scope="session")
def engine(dataset_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Engine:
    url = os.environ.get("EE_TEST_DATABASE_URL")
    if url:
        if not url.rstrip("/").endswith("_test"):
            raise RuntimeError("EE_TEST_DATABASE_URL must name a dedicated *_test database (schema is reset)")
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:  # start from an empty database every session
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        admin.dispose()
    else:
        url = f"sqlite:///{(tmp_path_factory.mktemp('db') / 'test.db').as_posix()}"
    upgrade_head(url)
    eng = make_engine(url)
    load_dataset(dataset_dir, eng)
    return eng
