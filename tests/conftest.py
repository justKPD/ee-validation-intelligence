from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ee_domain.snapshot import ValidationSnapshot, build_snapshot
from ee_etl.importer import read_dataset


@pytest.fixture(scope="session")
def dataset(dataset_dir: Path) -> dict[str, list[Any]]:
    data, _ = read_dataset(dataset_dir)
    return data


@pytest.fixture(scope="session")
def snap_b004(dataset: dict[str, list[Any]]) -> ValidationSnapshot:
    return build_snapshot(dataset, "B004")


@pytest.fixture(scope="session")
def snap_b006(dataset: dict[str, list[Any]]) -> ValidationSnapshot:
    return build_snapshot(dataset, "B006")
