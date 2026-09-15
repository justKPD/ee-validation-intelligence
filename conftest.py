"""Shared fixtures: one generated programme + one migrated SQLite DB per test session."""

from __future__ import annotations

from pathlib import Path

import pytest
from ee_domain.db import make_engine
from ee_etl.importer import load_dataset
from ee_etl.migrate import upgrade_head
from ee_generator import GeneratedProgramme, generate_programme, write_programme
from sqlalchemy import Engine


@pytest.fixture(scope="session")
def programme() -> GeneratedProgramme:
    return generate_programme(seed=42)


@pytest.fixture(scope="session")
def dataset_dir(programme: GeneratedProgramme, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_programme(programme, tmp_path_factory.mktemp("synthetic"))


@pytest.fixture(scope="session")
def engine(dataset_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Engine:
    url = f"sqlite:///{(tmp_path_factory.mktemp('db') / 'test.db').as_posix()}"
    upgrade_head(url)
    eng = make_engine(url)
    load_dataset(dataset_dir, eng)
    return eng
