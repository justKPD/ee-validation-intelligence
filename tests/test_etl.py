from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from ee_domain import models as m
from ee_domain.db import make_engine
from ee_etl.importer import DataQualityError, load_dataset, read_dataset
from ee_etl.migrate import upgrade_head
from ee_etl.quality import run_quality_checks
from ee_etl.report import dataset_summary_markdown
from ee_generator import GeneratedProgramme
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.orm import Session


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "dataset"
    shutil.copytree(src, dst)
    return dst


def _mutate(path: Path, name: str, fn) -> None:  # type: ignore[no-untyped-def]
    rows = json.loads((path / f"{name}.json").read_text())
    fn(rows)
    (path / f"{name}.json").write_text(json.dumps(rows))


def test_loaded_counts_match_manifest(engine: Engine, programme: GeneratedProgramme) -> None:
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(m.TestExecution)) == programme.counts["executions"]
        assert s.scalar(select(func.count()).select_from(m.Defect)) == programme.counts["defects"]
        assert s.scalar(select(func.count()).select_from(m.Component)) == 40


def test_migration_creates_all_authoritative_tables(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    for model in m.AUTHORITATIVE_TABLES_IN_LOAD_ORDER:
        assert model.__tablename__ in tables
    assert "alembic_version" in tables
    assert "risk_assessment" not in tables  # engines compute risk on demand; no stored authority copy


def test_checksum_tamper_is_rejected(dataset_dir: Path, tmp_path: Path) -> None:
    d = _copy(dataset_dir, tmp_path)
    (d / "components.json").write_text((d / "components.json").read_text().replace("Alpha", "Omega"))
    with pytest.raises(DataQualityError, match="checksum"):
        read_dataset(d)


def test_schema_violation_is_rejected(dataset_dir: Path, tmp_path: Path) -> None:
    d = _copy(dataset_dir, tmp_path)
    _mutate(d, "requirements", lambda rows: rows[0].update(severity=9))
    with pytest.raises(DataQualityError, match="severity"):
        read_dataset(d, verify_checksums=False)


def test_dangling_reference_is_rejected(dataset_dir: Path, tmp_path: Path) -> None:
    d = _copy(dataset_dir, tmp_path)
    _mutate(d, "defects", lambda rows: rows[0].update(component_id="ECU-NOPE"))
    data, _ = read_dataset(d, verify_checksums=False)
    report = run_quality_checks(data)
    assert any("defects.component_id" in e for e in report.errors)


def test_defect_on_passing_execution_is_rejected(dataset_dir: Path, tmp_path: Path) -> None:
    d = _copy(dataset_dir, tmp_path)
    data, _ = read_dataset(d)
    passing = next(e for e in data["executions"] if e.verdict == "PASS")
    data["defects"][0] = data["defects"][0].model_copy(update={"execution_id": passing.id})
    assert any("non-FAIL" in e for e in run_quality_checks(data).errors)


def test_execution_on_non_applicable_variant_is_rejected(dataset_dir: Path) -> None:
    data, _ = read_dataset(dataset_dir)
    applicable = {(tv.test_id, tv.variant_id) for tv in data["test_variants"]}
    e = data["executions"][0]
    bad_variant = next(v.id for v in data["variants"] if (e.test_id, v.id) not in applicable)
    data["executions"][0] = e.model_copy(update={"variant_id": bad_variant})
    assert any("non-applicable" in err for err in run_quality_checks(data).errors)


def test_size_target_violation_detected(dataset_dir: Path) -> None:
    data, _ = read_dataset(dataset_dir)
    data["components"] = data["components"][:10]
    assert any("size target" in err for err in run_quality_checks(data).errors)
    assert not any(
        "size target" in err for err in run_quality_checks(data, enforce_size_targets=False).errors
    )


def test_failed_import_leaves_previous_data_intact(engine: Engine, dataset_dir: Path, tmp_path: Path) -> None:
    d = _copy(dataset_dir, tmp_path)
    _mutate(d, "executions", lambda rows: rows[0].update(build_id="B999"))
    with pytest.raises(DataQualityError):
        load_dataset(d, engine)
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(m.Component)) == 40


def test_reimport_is_idempotent(dataset_dir: Path, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'idem.db').as_posix()}"
    upgrade_head(url)
    eng = make_engine(url)
    first = load_dataset(dataset_dir, eng).counts
    second = load_dataset(dataset_dir, eng).counts
    assert first == second
    with Session(eng) as s:
        assert s.scalar(select(func.count()).select_from(m.Requirement)) == 150


def test_summary_report_is_built_from_database(engine: Engine) -> None:
    md = dataset_summary_markdown(engine)
    assert "Entirely fictional synthetic data" in md
    assert "| Components | 40 |" in md
    assert "| B006 |" in md
